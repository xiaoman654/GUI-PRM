import argparse

from mobile_gui_agent_data.scorer.dataset import scorer_records_from_pair
from mobile_gui_agent_data.schemas import PreferencePair
from mobile_gui_agent_data.utils.io import read_jsonl, write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Preference pair JSONL")
    parser.add_argument("--output", required=True, help="Yes/No scorer JSONL")
    args = parser.parse_args()

    def records():
        for raw in read_jsonl(args.input):
            pair = PreferencePair(**raw)
            yield from scorer_records_from_pair(pair)

    write_jsonl(args.output, records())


if __name__ == "__main__":
    main()
