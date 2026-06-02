import argparse
import html
import json
from collections import Counter
from pathlib import Path
from typing import Any


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    records = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def write_jsonl(path: str | Path, records: list[dict[str, Any]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def candidate_action_type(record: dict[str, Any]) -> str:
    action = record.get("candidate_action") or {}
    return str(action.get("type", "unknown"))


def is_error(record: dict[str, Any]) -> bool:
    if "correct" in record:
        return not bool(record["correct"])
    return str(record.get("label")) != str(record.get("prediction_label"))


def image_src(image: str, image_root: str | Path | None) -> str:
    image_path = Path(image)
    if not image_path.is_absolute() and image_root is not None:
        image_path = Path(image_root) / image_path
    if image_path.is_absolute():
        return image_path.as_uri()
    return html.escape(image_path.as_posix())


def render_html(records: list[dict[str, Any]], output_path: str | Path, limit: int, image_root: str | Path | None) -> None:
    html_path = Path(output_path)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    shown_records = records[:limit]

    cards = []
    for idx, record in enumerate(shown_records, start=1):
        label = html.escape(str(record.get("label", "")))
        pred = html.escape(str(record.get("prediction_label", "")))
        negative_type = html.escape(str(record.get("negative_type", "")))
        action_type = html.escape(candidate_action_type(record))
        instruction = html.escape(str(record.get("instruction", "")))
        action = html.escape(str(record.get("candidate_action_text", "")))
        raw_pred = html.escape(str(record.get("prediction_raw", "")))
        src = image_src(str(record.get("image", "")), image_root)
        cards.append(
            f"""
            <section class="card">
              <div class="meta">
                <strong>#{idx}</strong>
                <span>{label} -> {pred}</span>
                <span>{negative_type}</span>
                <span>{action_type}</span>
              </div>
              <img src="{src}" alt="screen {idx}" />
              <div class="text"><strong>Instruction</strong><br>{instruction}</div>
              <div class="text"><strong>Candidate</strong><br><code>{action}</code></div>
              <div class="text"><strong>Raw prediction</strong><br><code>{raw_pred}</code></div>
            </section>
            """
        )

    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Scorer Error Inspection</title>
  <style>
    body {{
      margin: 0;
      font-family: Arial, sans-serif;
      background: #f6f7f9;
      color: #17191f;
    }}
    header {{
      position: sticky;
      top: 0;
      padding: 16px 24px;
      background: #ffffff;
      border-bottom: 1px solid #d9dde5;
      z-index: 1;
    }}
    main {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 16px;
      padding: 16px;
    }}
    .card {{
      background: #ffffff;
      border: 1px solid #d9dde5;
      border-radius: 8px;
      overflow: hidden;
    }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      padding: 10px;
      font-size: 13px;
      border-bottom: 1px solid #eceff4;
    }}
    .meta span {{
      padding: 2px 6px;
      background: #eef1f6;
      border-radius: 4px;
    }}
    img {{
      display: block;
      width: 100%;
      max-height: 520px;
      object-fit: contain;
      background: #111318;
    }}
    .text {{
      padding: 10px;
      font-size: 13px;
      line-height: 1.45;
      border-top: 1px solid #eceff4;
      overflow-wrap: anywhere;
    }}
    code {{
      font-family: Consolas, Menlo, monospace;
    }}
  </style>
</head>
<body>
  <header>
    <strong>Scorer Error Inspection</strong>
    <span>{len(records)} errors, showing {len(shown_records)}</span>
  </header>
  <main>
    {''.join(cards)}
  </main>
</body>
</html>
"""
    html_path.write_text(document, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Prediction JSONL produced by evaluate_qwen_vl_scorer.py")
    parser.add_argument("--summary-output", required=True)
    parser.add_argument("--errors-output", default=None)
    parser.add_argument("--html-output", default=None)
    parser.add_argument("--image-root", default=None)
    parser.add_argument("--focus", default=None, help="Optional confusion filter, such as No->Yes")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    records = read_jsonl(args.input)
    errors = [record for record in records if is_error(record)]
    if args.focus:
        errors = [
            record
            for record in errors
            if f"{record.get('label')}->{record.get('prediction_label')}" == args.focus
        ]

    summary = {
        "input": args.input,
        "num_records": len(records),
        "num_errors": len(errors),
        "focus": args.focus,
        "error_confusion": dict(
            Counter(f"{record.get('label')}->{record.get('prediction_label')}" for record in errors).most_common()
        ),
        "negative_type": dict(
            Counter(record.get("negative_type") for record in errors if str(record.get("label")) == "No").most_common()
        ),
        "candidate_action_type": dict(Counter(candidate_action_type(record) for record in errors).most_common()),
        "instructions": dict(Counter(str(record.get("instruction", "")) for record in errors).most_common(20)),
    }

    summary_path = Path(args.summary_output)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.errors_output:
        write_jsonl(args.errors_output, errors)
    if args.html_output:
        render_html(errors, args.html_output, args.limit, args.image_root)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
