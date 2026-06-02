import argparse

from mobile_gui_agent_data.datasets.selection import select_quality_difficulty_diversity
from mobile_gui_agent_data.utils.io import read_jsonl, write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Audited step JSONL")
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-samples", type=int, default=200)
    parser.add_argument("--min-quality", default="high", choices=["low", "medium", "high"])
    parser.add_argument("--per-action-limit", type=int, default=None)
    args = parser.parse_args()

    records = list(read_jsonl(args.input))
    selected = select_quality_difficulty_diversity(
        records,
        max_samples=args.max_samples,
        min_quality=args.min_quality,
        per_action_limit=args.per_action_limit,
    )
    write_jsonl(args.output, selected)


if __name__ == "__main__":
    main()
