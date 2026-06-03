import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_named_paths(values: list[str] | None) -> dict[str, str]:
    paths = {}
    for value in values or []:
        if "=" not in value:
            raise ValueError(f"Expected NAME=PATH, got {value!r}")
        name, path = value.split("=", 1)
        paths[name] = path
    return paths


def metric(report: dict[str, Any], path: list[str], default: Any = None) -> Any:
    current: Any = report
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def summarize_eval(report: dict[str, Any], error_summary: dict[str, Any] | None) -> dict[str, Any]:
    confusion = report.get("confusion", {})
    summary = {
        "num_samples": report.get("num_samples"),
        "accuracy": report.get("accuracy"),
        "yes_accuracy": metric(report, ["by_label", "Yes", "accuracy"]),
        "no_accuracy": metric(report, ["by_label", "No", "accuracy"]),
        "false_positive_no_to_yes": confusion.get("No->Yes", 0),
        "false_negative_yes_to_no": confusion.get("Yes->No", 0),
        "prediction_counts": report.get("prediction_counts", {}),
        "negative_type_no_accuracy": report.get("by_negative_type_no_only", {}),
        "negative_subtype_no_accuracy": report.get("by_negative_subtype_no_only", {}),
        "candidate_action_type_accuracy": report.get("by_candidate_action_type", {}),
    }
    if error_summary is not None:
        summary["false_positive_error_summary"] = {
            "num_errors": error_summary.get("num_errors"),
            "negative_type": error_summary.get("negative_type", {}),
            "candidate_action_type": error_summary.get("candidate_action_type", {}),
            "distance_bucket": error_summary.get("distance_bucket", {}),
            "candidate_in_ui_element": error_summary.get("candidate_in_ui_element", {}),
            "same_element_as_gt": error_summary.get("same_element_as_gt", {}),
        }
    return summary


def fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    if value is None:
        return ""
    return str(value)


def markdown_table(comparison: dict[str, Any]) -> str:
    rows = [
        [
            "run",
            "samples",
            "accuracy",
            "yes_acc",
            "no_acc",
            "No->Yes",
            "Yes->No",
            "random_acc",
            "same_screen_acc",
            "shifted_acc",
            "swipe_acc",
        ],
    ]
    for name, summary in comparison["runs"].items():
        random_acc = metric(summary, ["negative_type_no_accuracy", "random_coordinate", "accuracy"])
        same_screen_acc = metric(summary, ["negative_type_no_accuracy", "same_screen_element", "accuracy"])
        shifted_acc = metric(summary, ["negative_type_no_accuracy", "shifted_coordinate", "accuracy"])
        swipe_acc = metric(summary, ["candidate_action_type_accuracy", "swipe", "accuracy"])
        rows.append(
            [
                name,
                summary.get("num_samples"),
                summary.get("accuracy"),
                summary.get("yes_accuracy"),
                summary.get("no_accuracy"),
                summary.get("false_positive_no_to_yes"),
                summary.get("false_negative_yes_to_no"),
                random_acc,
                same_screen_acc,
                shifted_acc,
                swipe_acc,
            ]
        )
    widths = [max(len(fmt(row[idx])) for row in rows) for idx in range(len(rows[0]))]
    lines = []
    for row_idx, row in enumerate(rows):
        line = "| " + " | ".join(fmt(cell).ljust(widths[idx]) for idx, cell in enumerate(row)) + " |"
        lines.append(line)
        if row_idx == 0:
            lines.append("| " + " | ".join("-" * width for width in widths) + " |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval", action="append", help="NAME=eval_report.json", required=True)
    parser.add_argument("--error-summary", action="append", help="NAME=false_positive_error_summary.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--markdown-output", default=None)
    args = parser.parse_args()

    eval_paths = parse_named_paths(args.eval)
    error_paths = parse_named_paths(args.error_summary)
    comparison = {"runs": {}}
    for name, eval_path in eval_paths.items():
        error_summary = load_json(error_paths[name]) if name in error_paths else None
        comparison["runs"][name] = summarize_eval(load_json(eval_path), error_summary)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")

    markdown = markdown_table(comparison)
    if args.markdown_output:
        markdown_path = Path(args.markdown_output)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
    print(markdown)


if __name__ == "__main__":
    main()
