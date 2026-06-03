import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from mobile_gui_agent_data.utils.io import read_jsonl


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


def candidate_action(record: dict[str, Any]) -> dict[str, Any]:
    action = record.get("candidate_action") or {}
    return action if isinstance(action, dict) else {}


def candidate_action_type(record: dict[str, Any]) -> str:
    return str(candidate_action(record).get("type", "unknown"))


def negative_subtype(record: dict[str, Any]) -> str:
    metadata = candidate_action(record).get("metadata") or {}
    if not isinstance(metadata, dict):
        return "unknown"
    return str(metadata.get("negative_subtype") or metadata.get("negative_source") or "unknown")


def update_metric(metrics: dict[str, dict[str, int]], key: str, is_correct: bool) -> None:
    metrics[key]["total"] += 1
    metrics[key]["correct"] += int(is_correct)


def summarize_predictions(path: str | Path) -> dict[str, Any]:
    records = list(read_jsonl(path))
    prediction_counts = Counter()
    confusion = Counter()
    label_metrics: dict[str, dict[str, int]] = defaultdict(empty_metric)
    action_type_metrics: dict[str, dict[str, int]] = defaultdict(empty_metric)
    negative_type_metrics: dict[str, dict[str, int]] = defaultdict(empty_metric)
    negative_subtype_metrics: dict[str, dict[str, int]] = defaultdict(empty_metric)
    negative_subtype_by_type: dict[str, Counter] = defaultdict(Counter)
    error_negative_subtype = Counter()
    correct = 0

    for record in records:
        gold_label = str(record.get("label", ""))
        predicted_label = str(record.get("prediction_label", ""))
        is_correct = bool(record.get("correct", predicted_label == gold_label))
        correct += int(is_correct)
        prediction_counts[predicted_label] += 1
        confusion[f"{gold_label}->{predicted_label}"] += 1

        update_metric(label_metrics, gold_label, is_correct)
        update_metric(action_type_metrics, candidate_action_type(record), is_correct)

        if gold_label == "No":
            negative_type = str(record.get("negative_type", "unknown"))
            subtype = negative_subtype(record)
            update_metric(negative_type_metrics, negative_type, is_correct)
            update_metric(negative_subtype_metrics, subtype, is_correct)
            negative_subtype_by_type[negative_type][subtype] += 1
            if not is_correct:
                error_negative_subtype[subtype] += 1

    total = len(records)
    return {
        "input": str(path),
        "num_samples": total,
        "accuracy": correct / total if total else 0.0,
        "correct": correct,
        "prediction_counts": dict(prediction_counts.most_common()),
        "confusion": dict(sorted(confusion.items())),
        "by_label": finalize_metrics(label_metrics),
        "by_candidate_action_type": finalize_metrics(action_type_metrics),
        "by_negative_type_no_only": finalize_metrics(negative_type_metrics),
        "by_negative_subtype_no_only": finalize_metrics(negative_subtype_metrics),
        "negative_subtype_by_type_no_only": {
            key: dict(counter.most_common())
            for key, counter in sorted(negative_subtype_by_type.items())
        },
        "error_negative_subtype_no_only": dict(error_negative_subtype.most_common()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Predictions JSONL from evaluate_qwen_vl_scorer.py")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    summary = summarize_predictions(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
