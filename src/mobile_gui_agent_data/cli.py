import typer
from rich import print

from mobile_gui_agent_data.audit.pipeline import AuditPipeline
from mobile_gui_agent_data.preference.builder import PreferenceBuilder
from mobile_gui_agent_data.schemas import StepSample
from mobile_gui_agent_data.utils.io import read_jsonl, write_jsonl

app = typer.Typer(help="Mobile GUI Agent data-centric toolkit.")


@app.command()
def audit(input_path: str, output_path: str) -> None:
    pipeline = AuditPipeline()

    def records():
        for raw in read_jsonl(input_path):
            step = StepSample(**raw)
            result = pipeline.audit_step(step)
            payload = step.model_dump(mode="json")
            payload["audit"] = result.model_dump(mode="json")
            yield payload

    write_jsonl(output_path, records())
    print(f"[green]Wrote audited steps to {output_path}[/green]")


@app.command()
def preferences(input_path: str, output_path: str) -> None:
    builder = PreferenceBuilder()

    def records():
        for raw in read_jsonl(input_path):
            raw.pop("audit", None)
            step = StepSample(**raw)
            for pair in builder.build_for_step(step):
                yield pair.model_dump(mode="json")

    write_jsonl(output_path, records())
    print(f"[green]Wrote preference pairs to {output_path}[/green]")


if __name__ == "__main__":
    app()
