import argparse

from mobile_gui_agent_data.datasets.registry import get_parser
from mobile_gui_agent_data.utils.io import read_records, write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, choices=["aitw", "android_control"])
    parser.add_argument("--input", required=True, help="Raw episode JSON or JSONL path")
    parser.add_argument("--output", required=True, help="Output step-level JSONL path")
    args = parser.parse_args()

    episode_parser = get_parser(args.source)

    def records():
        for raw_episode in read_records(args.input):
            for step in episode_parser.parse(raw_episode):
                yield step.model_dump(mode="json")

    write_jsonl(args.output, records())


if __name__ == "__main__":
    main()
