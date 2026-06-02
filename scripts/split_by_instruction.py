import argparse

from mobile_gui_agent_data.datasets.split import instruction_wise_split
from mobile_gui_agent_data.schemas import StepSample
from mobile_gui_agent_data.utils.io import read_jsonl, write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--val-ratio", type=float, default=0.1)
    args = parser.parse_args()

    steps = [StepSample(**raw) for raw in read_jsonl(args.input)]
    splits = instruction_wise_split(steps, args.train_ratio, args.val_ratio)

    for split_name, split_steps in splits.items():
        output_path = f"{args.output_dir}/{split_name}.jsonl"
        write_jsonl(output_path, (step.model_dump(mode="json") for step in split_steps))


if __name__ == "__main__":
    main()
