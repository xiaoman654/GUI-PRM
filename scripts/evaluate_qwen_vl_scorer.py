import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import torch
import yaml
from peft import PeftModel
from tqdm import tqdm
from transformers import AutoProcessor

from train_qwen_vl_scorer import build_messages, load_model_class, read_jsonl

try:
    from qwen_vl_utils import process_vision_info
except ImportError as exc:  # pragma: no cover - environment check catches this.
    raise RuntimeError("qwen-vl-utils is required for Qwen2.5-VL evaluation.") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/scorer_qwen2_5_vl_lora.yaml")
    parser.add_argument("--input", required=True)
    parser.add_argument("--image-root", default=None)
    parser.add_argument("--output", required=True)
    parser.add_argument("--predictions-output", default=None)
    parser.add_argument("--model-name-or-path", default=None)
    parser.add_argument("--adapter-path", required=True)
    parser.add_argument("--attn-implementation", default=None)
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument("--max-new-tokens", type=int, default=4)
    return parser.parse_args()


def normalize_prediction(text: str) -> str:
    cleaned = text.strip().lower()
    if cleaned.startswith("yes"):
        return "Yes"
    if cleaned.startswith("no"):
        return "No"
    tokens = cleaned.replace(".", " ").replace(",", " ").split()
    if "yes" in tokens and "no" not in tokens:
        return "Yes"
    if "no" in tokens and "yes" not in tokens:
        return "No"
    return "Unknown"


def candidate_action_type(record: dict[str, Any]) -> str:
    action = record.get("candidate_action") or {}
    return str(action.get("type", "unknown"))


def empty_metric() -> dict[str, int]:
    return {"total": 0, "correct": 0}


def finalize_metrics(metrics: dict[str, dict[str, int]]) -> dict[str, dict[str, float | int]]:
    finalized = {}
    for key, value in sorted(metrics.items()):
        total = value["total"]
        correct = value["correct"]
        finalized[key] = {
            "total": total,
            "correct": correct,
            "accuracy": correct / total if total else 0.0,
        }
    return finalized


def load_model_and_processor(
    config: dict[str, Any],
    model_name: str,
    adapter_path: str,
    attn_implementation: str | None,
):
    model_config = config["model"]
    torch_dtype = torch.bfloat16 if model_config.get("torch_dtype") == "bfloat16" else torch.float16

    processor = AutoProcessor.from_pretrained(
        model_name,
        min_pixels=config["data"].get("min_pixels"),
        max_pixels=config["data"].get("max_pixels"),
        trust_remote_code=True,
    )

    model_cls = load_model_class()
    model_kwargs = {
        "torch_dtype": torch_dtype,
        "device_map": None,
        "trust_remote_code": True,
    }
    resolved_attn = attn_implementation or model_config.get("attn_implementation")
    if resolved_attn:
        model_kwargs["attn_implementation"] = resolved_attn

    try:
        base_model = model_cls.from_pretrained(model_name, **model_kwargs)
    except Exception:
        if model_kwargs.pop("attn_implementation", None) is not None:
            base_model = model_cls.from_pretrained(model_name, **model_kwargs)
        else:
            raise

    model = PeftModel.from_pretrained(base_model, adapter_path)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()
    return model, processor, device


def generate_prediction(
    model,
    processor,
    record: dict[str, Any],
    image_root: str | Path,
    system_prompt: str,
    question: str,
    device: torch.device,
    max_new_tokens: int,
) -> tuple[str, str]:
    messages = build_messages(
        record,
        image_root=image_root,
        system_prompt=system_prompt,
        question=question,
        include_answer=False,
    )
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    ).to(device)

    with torch.no_grad():
        generated_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
        )
    prompt_length = inputs["input_ids"].shape[1]
    answer_ids = generated_ids[:, prompt_length:]
    raw_prediction = processor.batch_decode(
        answer_ids,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )[0]
    return raw_prediction, normalize_prediction(raw_prediction)


def main() -> None:
    args = parse_args()
    with Path(args.config).open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    model_name = args.model_name_or_path or config["model"]["name_or_path"]
    image_root = args.image_root or config["data"].get("image_root", ".")
    prompt_config = config["prompt"]
    records = read_jsonl(args.input, args.max_samples)

    model, processor, device = load_model_and_processor(
        config=config,
        model_name=model_name,
        adapter_path=args.adapter_path,
        attn_implementation=args.attn_implementation,
    )

    prediction_counts = Counter()
    label_metrics: dict[str, dict[str, int]] = defaultdict(empty_metric)
    negative_type_metrics: dict[str, dict[str, int]] = defaultdict(empty_metric)
    action_type_metrics: dict[str, dict[str, int]] = defaultdict(empty_metric)
    confusion = Counter()
    correct = 0
    prediction_rows = []

    for record in tqdm(records, desc="evaluating"):
        raw_prediction, predicted_label = generate_prediction(
            model=model,
            processor=processor,
            record=record,
            image_root=image_root,
            system_prompt=prompt_config["system"],
            question=prompt_config["question"],
            device=device,
            max_new_tokens=args.max_new_tokens,
        )
        gold_label = str(record.get("label", ""))
        is_correct = predicted_label == gold_label
        correct += int(is_correct)
        prediction_counts[predicted_label] += 1
        confusion[f"{gold_label}->{predicted_label}"] += 1

        label_metrics[gold_label]["total"] += 1
        label_metrics[gold_label]["correct"] += int(is_correct)

        action_type = candidate_action_type(record)
        action_type_metrics[action_type]["total"] += 1
        action_type_metrics[action_type]["correct"] += int(is_correct)

        if gold_label == "No":
            negative_type = str(record.get("negative_type", "unknown"))
            negative_type_metrics[negative_type]["total"] += 1
            negative_type_metrics[negative_type]["correct"] += int(is_correct)

        if args.predictions_output:
            prediction_row = dict(record)
            prediction_row["prediction_raw"] = raw_prediction
            prediction_row["prediction_label"] = predicted_label
            prediction_row["correct"] = is_correct
            prediction_rows.append(prediction_row)

    total = len(records)
    report = {
        "input": args.input,
        "model_name_or_path": model_name,
        "adapter_path": args.adapter_path,
        "num_samples": total,
        "accuracy": correct / total if total else 0.0,
        "correct": correct,
        "prediction_counts": dict(prediction_counts.most_common()),
        "confusion": dict(sorted(confusion.items())),
        "by_label": finalize_metrics(label_metrics),
        "by_negative_type_no_only": finalize_metrics(negative_type_metrics),
        "by_candidate_action_type": finalize_metrics(action_type_metrics),
        "max_new_tokens": args.max_new_tokens,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    if args.predictions_output:
        predictions_path = Path(args.predictions_output)
        predictions_path.parent.mkdir(parents=True, exist_ok=True)
        with predictions_path.open("w", encoding="utf-8") as f:
            for row in prediction_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
