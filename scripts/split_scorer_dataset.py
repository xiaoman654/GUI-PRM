import argparse
from pathlib import Path

from mobile_gui_agent_data.scorer.split import instruction_wise_split_records
from mobile_gui_agent_data.utils.io import read_jsonl, write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--val-ratio", type=float, default=0.1)
    args = parser.parse_args()

    records = list(read_jsonl(args.input))
    splits = instruction_wise_split_records(records, args.train_ratio, args.val_ratio)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for split_name, split_records in splits.items():
        write_jsonl(output_dir / f"{split_name}.jsonl", split_records)


if __name__ == "__main__":
    main()
