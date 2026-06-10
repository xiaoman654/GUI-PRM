import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from mobile_gui_agent_data.scorer.dataset import scorer_records_from_pair
from mobile_gui_agent_data.scorer.split import instruction_wise_split_records
from mobile_gui_agent_data.schemas import PreferencePair
from mobile_gui_agent_data.utils.io import read_jsonl, write_jsonl


VARIANTS = {
    "clean_filter": {"drop_decisions": {"filter"}},
    "ambiguous_removed": {"drop_decisions": {"filter", "ambiguous"}},
}


def load_decisions(path: Path) -> dict[str, dict[str, Any]]:
    return {row["pair_id"]: row for row in read_jsonl(path)}


def pair_with_filter_metadata(pair: PreferencePair, decision: dict[str, Any]) -> dict[str, Any]:
    payload = pair.model_dump(mode="json")
    payload["metadata"] = {
        **payload.get("metadata", {}),
        "v3_filter_decision": decision.get("decision"),
        "v3_filter_reason": decision.get("reason"),
        "v3_major_category": decision.get("major_category"),
        "target_region_kind": decision.get("target_region_kind"),
        "candidate_region_kind": decision.get("candidate_region_kind"),
    }
    return payload


def summarize_pairs(records: list[dict[str, Any]], dropped: list[dict[str, Any]]) -> dict[str, Any]:
    kept_decisions = Counter(record.get("metadata", {}).get("v3_filter_decision", "unknown") for record in records)
    kept_categories = Counter(record.get("metadata", {}).get("v3_major_category", "unknown") for record in records)
    kept_negative_types = Counter(record.get("negative_type", "unknown") for record in records)
    dropped_decisions = Counter(record.get("decision", "unknown") for record in dropped)
    dropped_reasons = Counter(record.get("reason", "unknown") for record in dropped)
    dropped_negative_types = Counter(record.get("negative_type", "unknown") for record in dropped)
    dropped_by_type_reason: dict[str, Counter] = defaultdict(Counter)
    for record in dropped:
        dropped_by_type_reason[record.get("negative_type", "unknown")][record.get("reason", "unknown")] += 1

    return {
        "num_pairs": len(records),
        "num_scorer_records": len(records) * 2,
        "kept_decisions": dict(kept_decisions),
        "kept_major_categories": dict(kept_categories),
        "kept_negative_types": dict(kept_negative_types),
        "num_dropped_pairs": len(dropped),
        "dropped_decisions": dict(dropped_decisions),
        "dropped_reasons": dict(dropped_reasons),
        "dropped_negative_types": dict(dropped_negative_types),
        "dropped_by_negative_type_reason": {key: dict(value) for key, value in dropped_by_type_reason.items()},
    }


def write_splits(records: list[dict[str, Any]], output_dir: Path) -> dict[str, int]:
    splits = instruction_wise_split_records(records)
    output_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    for split_name, split_records in splits.items():
        write_jsonl(output_dir / f"{split_name}.jsonl", split_records)
        counts[split_name] = len(split_records)
    return counts


def build_variant(
    variant_name: str,
    drop_decisions: set[str],
    pairs: list[PreferencePair],
    decisions: dict[str, dict[str, Any]],
    preference_dir: Path,
    scorer_dir: Path,
    report_dir: Path,
    prefix: str,
) -> dict[str, Any]:
    kept_pairs = []
    dropped = []

    for pair in pairs:
        decision = decisions.get(pair.pair_id)
        if decision is None:
            raise KeyError(f"Missing decision for pair_id={pair.pair_id}")
        if decision["decision"] in drop_decisions:
            dropped.append(decision)
            continue
        kept_pairs.append(pair_with_filter_metadata(pair, decision))

    pairs_path = preference_dir / f"{prefix}_{variant_name}_pairs.jsonl"
    scorer_path = scorer_dir / f"{prefix}_{variant_name}_scorer_yesno.jsonl"
    split_dir = scorer_dir / f"{prefix}_{variant_name}_splits"
    summary_path = report_dir / f"{prefix}_{variant_name}_summary.json"

    write_jsonl(pairs_path, kept_pairs)

    scorer_records = []
    for payload in kept_pairs:
        pair = PreferencePair.model_validate(payload)
        scorer_records.extend(scorer_records_from_pair(pair))
    write_jsonl(scorer_path, scorer_records)
    split_counts = write_splits(scorer_records, split_dir)

    summary = {
        "variant": variant_name,
        "drop_decisions": sorted(drop_decisions),
        "pairs": str(pairs_path),
        "scorer": str(scorer_path),
        "splits": str(split_dir),
        "split_counts": split_counts,
        **summarize_pairs(kept_pairs, dropped),
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return {**summary, "summary": str(summary_path)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", required=True)
    parser.add_argument("--decisions", required=True)
    parser.add_argument("--prefix", default="unseen_subject_train_1000_v3")
    parser.add_argument("--preference-dir", default="data/preferences/aitw_single")
    parser.add_argument("--scorer-dir", default="data/scorer/aitw_single")
    parser.add_argument("--report-dir", default="reports/aitw_single")
    args = parser.parse_args()

    pairs = [PreferencePair.model_validate(row) for row in read_jsonl(args.pairs)]
    decisions = load_decisions(Path(args.decisions))

    outputs = {}
    for variant_name, config in VARIANTS.items():
        outputs[variant_name] = build_variant(
            variant_name=variant_name,
            drop_decisions=config["drop_decisions"],
            pairs=pairs,
            decisions=decisions,
            preference_dir=Path(args.preference_dir),
            scorer_dir=Path(args.scorer_dir),
            report_dir=Path(args.report_dir),
            prefix=args.prefix,
        )

    print(json.dumps(outputs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
