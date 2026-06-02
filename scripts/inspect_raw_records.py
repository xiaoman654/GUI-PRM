import argparse
import json

from mobile_gui_agent_data.analysis.inspect import inspect_records
from mobile_gui_agent_data.utils.io import read_records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    report = inspect_records(read_records(args.input), limit=args.limit)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
