import argparse

from mobile_gui_agent_data.audit.pipeline import AuditPipeline
from mobile_gui_agent_data.schemas import StepSample
from mobile_gui_agent_data.utils.io import read_jsonl, write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    pipeline = AuditPipeline()

    def records():
        for raw in read_jsonl(args.input):
            step = StepSample(**raw)
            result = pipeline.audit_step(step)
            payload = step.model_dump(mode="json")
            payload["audit"] = result.model_dump(mode="json")
            yield payload

    write_jsonl(args.output, records())


if __name__ == "__main__":
    main()
