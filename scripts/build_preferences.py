import argparse

from mobile_gui_agent_data.preference.builder import PreferenceBuilder
from mobile_gui_agent_data.schemas import StepSample
from mobile_gui_agent_data.utils.io import read_jsonl, write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    builder = PreferenceBuilder()

    def records():
        for raw in read_jsonl(args.input):
            raw.pop("audit", None)
            step = StepSample(**raw)
            for pair in builder.build_for_step(step):
                yield pair.model_dump(mode="json")

    write_jsonl(args.output, records())


if __name__ == "__main__":
    main()
