import argparse

from mobile_gui_agent_data.datasets.transforms import step_to_coordinate_space
from mobile_gui_agent_data.schemas import StepSample
from mobile_gui_agent_data.utils.io import read_jsonl, write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--coordinate-space",
        default="normalized_1000",
        choices=["pixel", "normalized_1000", "normalized_1"],
    )
    args = parser.parse_args()

    def records():
        for raw in read_jsonl(args.input):
            step = StepSample(**raw)
            yield step_to_coordinate_space(step, args.coordinate_space).model_dump(mode="json")

    write_jsonl(args.output, records())


if __name__ == "__main__":
    main()
