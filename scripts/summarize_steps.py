import argparse
import json

from mobile_gui_agent_data.analysis.stats import summarize_steps
from mobile_gui_agent_data.schemas import StepSample
from mobile_gui_agent_data.utils.io import read_jsonl


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    steps = [StepSample(**raw) for raw in read_jsonl(args.input)]
    summary = summarize_steps(steps)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
