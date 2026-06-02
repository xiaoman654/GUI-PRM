import argparse
import json
from pathlib import Path

from mobile_gui_agent_data.scorer.summary import summarize_scorer_records
from mobile_gui_agent_data.utils.io import read_jsonl


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--image-root", default=None)
    args = parser.parse_args()

    records = list(read_jsonl(args.input))
    summary = summarize_scorer_records(records, image_root=args.image_root)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
