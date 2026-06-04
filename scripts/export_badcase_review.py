import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from inspect_scorer_errors import candidate_action_type, candidate_negative_subtype, enrich_error, load_pair_index


REVIEW_LABELS = [
    "label_noise",
    "ambiguous_alternative",
    "same_functional_region",
    "semantic_hard_negative",
    "swipe_uncertain",
    "true_clean_negative",
]


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    records = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def compact_text(value: Any, max_len: int = 220) -> str:
    text = "" if value is None else str(value).replace("\r", " ").replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def row_from_record(index: int, record: dict[str, Any]) -> dict[str, Any]:
    candidate = record.get("candidate_action") or {}
    gt_action = record.get("gt_action") or {}
    return {
        "case_index": index,
        "review_label": "",
        "notes": "",
        "suggested_labels": "|".join(REVIEW_LABELS),
        "label": record.get("label", ""),
        "prediction": record.get("prediction_label", ""),
        "negative_type": record.get("negative_type", ""),
        "negative_subtype": candidate_negative_subtype(record),
        "candidate_action_type": candidate_action_type(record),
        "distance_px": record.get("distance_px", ""),
        "distance_bucket": record.get("distance_bucket", ""),
        "candidate_in_ui_element": record.get("candidate_in_ui_element", ""),
        "same_element_as_gt": record.get("same_element_as_gt", ""),
        "instruction": compact_text(record.get("instruction", ""), 300),
        "candidate_action_text": compact_text(record.get("candidate_action_text", ""), 260),
        "gt_action_text": compact_text(record.get("gt_action_text", ""), 260),
        "candidate_element_text": compact_text(record.get("candidate_element_text", ""), 180),
        "candidate_element_type": (record.get("candidate_element") or {}).get("ui_type", ""),
        "gt_element_text": compact_text(record.get("gt_element_text", ""), 180),
        "gt_element_type": (record.get("gt_element") or {}).get("ui_type", ""),
        "image": record.get("image", ""),
        "sample_id": record.get("sample_id", ""),
        "pair_id": record.get("pair_id", ""),
        "candidate_action_json": json.dumps(candidate, ensure_ascii=False),
        "gt_action_json": json.dumps(gt_action, ensure_ascii=False),
    }


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "num_badcases": len(records),
        "negative_type": dict(Counter(str(r.get("negative_type", "")) for r in records).most_common()),
        "negative_subtype": dict(Counter(candidate_negative_subtype(r) for r in records).most_common()),
        "candidate_action_type": dict(Counter(candidate_action_type(r) for r in records).most_common()),
        "distance_bucket": dict(Counter(str(r.get("distance_bucket", "unknown")) for r in records).most_common()),
        "candidate_in_ui_element": dict(Counter(str(r.get("candidate_in_ui_element", "unknown")) for r in records).most_common()),
        "same_element_as_gt": dict(Counter(str(r.get("same_element_as_gt", "unknown")) for r in records).most_common()),
        "top_instructions": dict(Counter(str(r.get("instruction", "")) for r in records).most_common(20)),
    }


def write_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else [
        "case_index",
        "review_label",
        "notes",
        "suggested_labels",
    ]
    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: str | Path, rows: list[dict[str, Any]], limit: int) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Badcase Review",
        "",
        "Review labels:",
        "",
        *[f"- `{label}`" for label in REVIEW_LABELS],
        "",
    ]
    for row in rows[:limit]:
        lines.extend(
            [
                f"## Case {row['case_index']}",
                "",
                f"- label/prediction: `{row['label']} -> {row['prediction']}`",
                f"- negative: `{row['negative_type']} / {row['negative_subtype']}`",
                f"- action type: `{row['candidate_action_type']}`",
                f"- distance: `{row['distance_bucket']}`",
                f"- candidate_in_ui_element: `{row['candidate_in_ui_element']}`",
                f"- same_element_as_gt: `{row['same_element_as_gt']}`",
                f"- instruction: {row['instruction']}",
                f"- candidate: `{row['candidate_action_text']}`",
                f"- ground truth: `{row['gt_action_text']}`",
                f"- candidate element: `{row['candidate_element_text']}` / `{row['candidate_element_type']}`",
                f"- gt element: `{row['gt_element_text']}` / `{row['gt_element_type']}`",
                f"- image: `{row['image']}`",
                "",
                "review_label:",
                "",
                "notes:",
                "",
            ]
        )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Badcase JSONL, usually *_false_positive_errors.jsonl")
    parser.add_argument("--pairs", default=None, help="Optional preference pairs JSONL to recover gt action/UI info")
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--summary-output", required=True)
    parser.add_argument("--markdown-output", default=None)
    parser.add_argument("--markdown-limit", type=int, default=80)
    parser.add_argument("--negative-subtype", default=None)
    parser.add_argument("--action-type", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pair_index = load_pair_index(args.pairs)
    records = []
    for record in read_jsonl(args.input):
        enriched = enrich_error(record, pair_index.get(str(record.get("pair_id"))))
        if args.negative_subtype and candidate_negative_subtype(enriched) != args.negative_subtype:
            continue
        if args.action_type and candidate_action_type(enriched) != args.action_type:
            continue
        records.append(enriched)

    rows = [row_from_record(index, record) for index, record in enumerate(records, start=1)]
    write_csv(args.output_csv, rows)
    summary = summarize(records)
    summary_path = Path(args.summary_output)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown_output:
        write_markdown(args.markdown_output, rows, args.markdown_limit)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
