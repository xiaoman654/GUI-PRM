import json
from pathlib import Path

from mobile_gui_agent_data.analysis.inspect import inspect_records
from mobile_gui_agent_data.analysis.stats import summarize_steps
from mobile_gui_agent_data.audit.pipeline import AuditPipeline
from mobile_gui_agent_data.datasets.aitw import AITWParser
from mobile_gui_agent_data.datasets.selection import select_quality_difficulty_diversity
from mobile_gui_agent_data.datasets.transforms import step_to_coordinate_space
from mobile_gui_agent_data.preference.builder import PreferenceBuilder
from mobile_gui_agent_data.schemas import StepSample
from mobile_gui_agent_data.utils.io import read_records, write_jsonl


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def reprocess_aitw_single_raw(
    raw_path: str | Path,
    tag: str,
    qdd_samples: int = 200,
    root: str | Path = ".",
) -> dict[str, str | int]:
    root = Path(root)
    raw_path = Path(raw_path)

    interim_dir = root / "data" / "interim" / "aitw_single"
    processed_dir = root / "data" / "processed" / "aitw_single"
    preference_dir = root / "data" / "preferences" / "aitw_single"
    report_dir = root / "reports" / "aitw_single"

    for directory in [interim_dir, processed_dir, preference_dir, report_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    raw_schema_path = report_dir / f"{tag}_raw_schema.json"
    steps_path = interim_dir / f"{tag}_steps.jsonl"
    norm_steps_path = interim_dir / f"{tag}_steps_norm1000.jsonl"
    summary_path = report_dir / f"{tag}_step_summary.json"
    audited_path = processed_dir / f"{tag}_audited.jsonl"
    pairs_path = preference_dir / f"{tag}_pairs.jsonl"
    qdd_path = processed_dir / f"{tag}_qdd_selected_{qdd_samples}.jsonl"

    write_json(raw_schema_path, inspect_records(read_records(raw_path), limit=50))

    aitw_parser = AITWParser()
    steps = [
        step
        for raw_record in read_records(raw_path)
        for step in aitw_parser.parse(raw_record)
    ]
    write_jsonl(steps_path, (step.model_dump(mode="json") for step in steps))

    norm_steps = [step_to_coordinate_space(step, "normalized_1000") for step in steps]
    write_jsonl(norm_steps_path, (step.model_dump(mode="json") for step in norm_steps))
    write_json(summary_path, summarize_steps(steps))

    audit_pipeline = AuditPipeline()
    audited_records = []
    for step in steps:
        result = audit_pipeline.audit_step(step)
        payload = step.model_dump(mode="json")
        payload["audit"] = result.model_dump(mode="json")
        audited_records.append(payload)
    write_jsonl(audited_path, audited_records)

    preference_builder = PreferenceBuilder()
    step_objects = [
        StepSample(**{key: value for key, value in record.items() if key != "audit"})
        for record in audited_records
    ]
    pairs = [pair for step in step_objects for pair in preference_builder.build_for_step(step)]
    write_jsonl(pairs_path, (pair.model_dump(mode="json") for pair in pairs))

    qdd_records = select_quality_difficulty_diversity(
        audited_records,
        max_samples=qdd_samples,
        min_quality="high",
    )
    write_jsonl(qdd_path, qdd_records)

    return {
        "raw": str(raw_path),
        "steps": str(steps_path),
        "normalized_steps": str(norm_steps_path),
        "summary": str(summary_path),
        "audited": str(audited_path),
        "pairs": str(pairs_path),
        "qdd": str(qdd_path),
        "num_steps": len(steps),
        "num_pairs": len(pairs),
    }
