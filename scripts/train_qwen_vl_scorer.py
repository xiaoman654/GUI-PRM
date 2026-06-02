import argparse
import json
import math
from pathlib import Path
from typing import Any

import torch
import yaml
from peft import LoraConfig, get_peft_model
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm
from transformers import AutoProcessor, get_cosine_schedule_with_warmup

try:
    from qwen_vl_utils import process_vision_info
except ImportError as exc:  # pragma: no cover - environment check catches this.
    raise RuntimeError("qwen-vl-utils is required for Qwen2.5-VL training.") from exc


def read_jsonl(path: str | Path, limit: int | None = None) -> list[dict[str, Any]]:
    records = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
            if limit is not None and len(records) >= limit:
                break
    return records


def load_model_class():
    try:
        from transformers import Qwen2_5_VLForConditionalGeneration

        return Qwen2_5_VLForConditionalGeneration
    except ImportError:
        from transformers import AutoModelForImageTextToText

        return AutoModelForImageTextToText


def resolve_image_path(image: str, image_root: str | Path) -> str:
    image_path = Path(image)
    if not image_path.is_absolute():
        image_path = Path(image_root) / image_path
    return str(image_path)


def candidate_prompt(record: dict[str, Any], question: str) -> str:
    return "\n".join(
        [
            f"Instruction: {record['instruction']}",
            f"Candidate action: {record['candidate_action_text']}",
            question,
            "Answer only Yes or No.",
        ]
    )


def build_messages(record: dict[str, Any], image_root: str | Path, system_prompt: str, question: str, include_answer: bool) -> list[dict[str, Any]]:
    user_content = [
        {"type": "image", "image": resolve_image_path(record["image"], image_root)},
        {"type": "text", "text": candidate_prompt(record, question)},
    ]
    messages = [
        {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
        {"role": "user", "content": user_content},
    ]
    if include_answer:
        messages.append({"role": "assistant", "content": [{"type": "text", "text": record["label"]}]})
    return messages


class ScorerDataset(Dataset):
    def __init__(self, records: list[dict[str, Any]]) -> None:
        self.records = records

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> dict[str, Any]:
        return self.records[index]


class QwenScorerCollator:
    def __init__(self, processor, image_root: str | Path, system_prompt: str, question: str) -> None:
        self.processor = processor
        self.image_root = image_root
        self.system_prompt = system_prompt
        self.question = question

    def __call__(self, batch: list[dict[str, Any]]) -> dict[str, torch.Tensor]:
        full_messages = [
            build_messages(record, self.image_root, self.system_prompt, self.question, include_answer=True)
            for record in batch
        ]
        prompt_messages = [
            build_messages(record, self.image_root, self.system_prompt, self.question, include_answer=False)
            for record in batch
        ]
        full_texts = [
            self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
            for messages in full_messages
        ]
        prompt_texts = [
            self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            for messages in prompt_messages
        ]

        full_image_inputs, full_video_inputs = process_vision_info(full_messages)
        prompt_image_inputs, prompt_video_inputs = process_vision_info(prompt_messages)

        full_inputs = self.processor(
            text=full_texts,
            images=full_image_inputs,
            videos=full_video_inputs,
            padding=True,
            return_tensors="pt",
        )
        prompt_inputs = self.processor(
            text=prompt_texts,
            images=prompt_image_inputs,
            videos=prompt_video_inputs,
            padding=True,
            return_tensors="pt",
        )

        labels = full_inputs["input_ids"].clone()
        labels[full_inputs["attention_mask"] == 0] = -100
        prompt_lengths = prompt_inputs["attention_mask"].sum(dim=1).tolist()
        for row_idx, prompt_length in enumerate(prompt_lengths):
            labels[row_idx, : int(prompt_length)] = -100
        full_inputs["labels"] = labels
        return full_inputs


def move_to_device(batch: dict[str, Any], device: torch.device) -> dict[str, Any]:
    return {
        key: value.to(device) if hasattr(value, "to") else value
        for key, value in batch.items()
    }


def evaluate(model, dataloader: DataLoader, device: torch.device, max_batches: int | None = None) -> float:
    model.eval()
    losses = []
    with torch.no_grad():
        for batch_idx, batch in enumerate(dataloader):
            batch = move_to_device(batch, device)
            output = model(**batch)
            losses.append(float(output.loss.detach().cpu()))
            if max_batches is not None and batch_idx + 1 >= max_batches:
                break
    model.train()
    return sum(losses) / max(len(losses), 1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/scorer_qwen2_5_vl_lora.yaml")
    parser.add_argument("--train-path", default=None)
    parser.add_argument("--val-path", default=None)
    parser.add_argument("--image-root", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--model-name-or-path", default=None)
    parser.add_argument("--attn-implementation", default=None)
    parser.add_argument("--max-train-samples", type=int, default=None)
    parser.add_argument("--max-val-samples", type=int, default=256)
    parser.add_argument("--max-steps", type=int, default=None)
    parser.add_argument("--eval-max-batches", type=int, default=20)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with Path(args.config).open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    model_name = args.model_name_or_path or config["model"]["name_or_path"]
    train_path = args.train_path or config["data"]["train_path"]
    val_path = args.val_path or config["data"]["val_path"]
    image_root = args.image_root or config["data"].get("image_root", ".")
    output_dir = Path(args.output_dir or config["training"]["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    training_config = config["training"]
    prompt_config = config["prompt"]
    model_config = config["model"]
    lora_config = config["lora"]

    torch_dtype = torch.bfloat16 if model_config.get("torch_dtype") == "bfloat16" else torch.float16
    attn_implementation = args.attn_implementation or model_config.get("attn_implementation")

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
    if attn_implementation:
        model_kwargs["attn_implementation"] = attn_implementation
    try:
        model = model_cls.from_pretrained(model_name, **model_kwargs)
    except Exception:
        if model_kwargs.pop("attn_implementation", None) is not None:
            model = model_cls.from_pretrained(model_name, **model_kwargs)
        else:
            raise

    if training_config.get("gradient_checkpointing", False):
        model.gradient_checkpointing_enable()
        model.enable_input_require_grads()

    peft_config = LoraConfig(
        r=lora_config["r"],
        lora_alpha=lora_config["alpha"],
        lora_dropout=lora_config["dropout"],
        target_modules=lora_config["target_modules"],
        bias="none",
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.train()

    train_records = read_jsonl(train_path, args.max_train_samples)
    val_records = read_jsonl(val_path, args.max_val_samples)

    collator = QwenScorerCollator(
        processor=processor,
        image_root=image_root,
        system_prompt=prompt_config["system"],
        question=prompt_config["question"],
    )
    train_loader = DataLoader(
        ScorerDataset(train_records),
        batch_size=training_config["per_device_train_batch_size"],
        shuffle=True,
        collate_fn=collator,
    )
    val_loader = DataLoader(
        ScorerDataset(val_records),
        batch_size=training_config["per_device_eval_batch_size"],
        shuffle=False,
        collate_fn=collator,
    )

    gradient_accumulation_steps = training_config["gradient_accumulation_steps"]
    total_update_steps = math.ceil(
        len(train_loader) * training_config["num_train_epochs"] / gradient_accumulation_steps
    )
    if args.max_steps is not None:
        total_update_steps = min(total_update_steps, args.max_steps)
    warmup_steps = int(total_update_steps * training_config.get("warmup_ratio", 0.0))

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=training_config["learning_rate"],
        weight_decay=training_config.get("weight_decay", 0.0),
    )
    scheduler = get_cosine_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=total_update_steps,
    )

    global_step = 0
    running_loss = 0.0
    optimizer.zero_grad(set_to_none=True)
    progress = tqdm(total=total_update_steps, desc="training")
    for _epoch in range(training_config["num_train_epochs"]):
        for batch_idx, batch in enumerate(train_loader):
            batch = move_to_device(batch, device)
            output = model(**batch)
            loss = output.loss / gradient_accumulation_steps
            loss.backward()
            running_loss += float(loss.detach().cpu()) * gradient_accumulation_steps

            if (batch_idx + 1) % gradient_accumulation_steps == 0:
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad(set_to_none=True)
                global_step += 1
                progress.update(1)

                if global_step % training_config["logging_steps"] == 0:
                    avg_loss = running_loss / training_config["logging_steps"]
                    progress.write(f"step={global_step} train_loss={avg_loss:.4f}")
                    running_loss = 0.0

                if global_step % training_config["eval_steps"] == 0:
                    eval_loss = evaluate(model, val_loader, device, args.eval_max_batches)
                    progress.write(f"step={global_step} eval_loss={eval_loss:.4f}")

                if global_step % training_config["save_steps"] == 0:
                    checkpoint_dir = output_dir / f"checkpoint-{global_step}"
                    model.save_pretrained(checkpoint_dir)
                    processor.save_pretrained(checkpoint_dir)

                if args.max_steps is not None and global_step >= args.max_steps:
                    break
        if args.max_steps is not None and global_step >= args.max_steps:
            break

    progress.close()
    model.save_pretrained(output_dir)
    processor.save_pretrained(output_dir)
    final_eval_loss = evaluate(model, val_loader, device, args.eval_max_batches)
    with (output_dir / "train_summary.json").open("w", encoding="utf-8") as f:
        json.dump(
            {
                "global_step": global_step,
                "final_eval_loss": final_eval_loss,
                "train_samples": len(train_records),
                "val_samples": len(val_records),
                "model_name_or_path": model_name,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )


if __name__ == "__main__":
    main()
