import argparse
import json
from pathlib import Path

from mobile_gui_agent_data.pipelines.aitw_single import reprocess_aitw_single_raw
from mobile_gui_agent_data.scorer.dataset import scorer_records_from_pair
from mobile_gui_agent_data.scorer.split import instruction_wise_split_records
from mobile_gui_agent_data.scorer.summary import summarize_scorer_records
from mobile_gui_agent_data.schemas import PreferencePair
from mobile_gui_agent_data.utils.io import read_jsonl, write_jsonl

from summarize_preference_pairs import summarize_pairs


def write_json(path: str | Path, payload: dict) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_scorer_records(pairs_path: str | Path, output_path: str | Path) -> int:
    count = 0

    def records():
        nonlocal count
        for raw in read_jsonl(pairs_path):
            pair = PreferencePair(**raw)
            for record in scorer_records_from_pair(pair):
                count += 1
                yield record

    write_jsonl(output_path, records())
    return count


def split_scorer_records(
    scorer_path: str | Path,
    split_dir: str | Path,
    train_ratio: float,
    val_ratio: float,
    image_root: str | Path,
    report_dir: str | Path,
    tag: str,
) -> dict[str, int]:
    records = list(read_jsonl(scorer_path))
    splits = instruction_wise_split_records(records, train_ratio=train_ratio, val_ratio=val_ratio)

    split_path = Path(split_dir)
    split_path.mkdir(parents=True, exist_ok=True)
    counts = {}
    for split_name, split_records in splits.items():
        counts[split_name] = len(split_records)
        write_jsonl(split_path / f"{split_name}.jsonl", split_records)
        write_json(
            Path(report_dir) / f"{tag}_scorer_{split_name}_summary.json",
            summarize_scorer_records(split_records, image_root=image_root),
        )
    return counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", required=True, help="Raw AITW_Single JSONL with images")
    parser.add_argument("--tag", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--qdd-samples", type=int, default=200)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--val-ratio", type=float, default=0.1)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root)
    scorer_dir = root / "data" / "scorer" / "aitw_single"
    report_dir = root / "reports" / "aitw_single"

    pipeline_result = reprocess_aitw_single_raw(
        raw_path=args.raw,
        tag=args.tag,
        qdd_samples=args.qdd_samples,
        root=root,
    )
    pairs_path = Path(str(pipeline_result["pairs"]))
    pair_summary_path = report_dir / f"{args.tag}_pair_summary.json"
    write_json(pair_summary_path, summarize_pairs(pairs_path))

    scorer_path = scorer_dir / f"{args.tag}_scorer_yesno.jsonl"
    num_scorer_records = build_scorer_records(pairs_path, scorer_path)

    split_dir = scorer_dir / f"{args.tag}_splits"
    split_counts = split_scorer_records(
        scorer_path=scorer_path,
        split_dir=split_dir,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        image_root=root,
        report_dir=report_dir,
        tag=args.tag,
    )

    result = {
        **pipeline_result,
        "pair_summary": str(pair_summary_path),
        "scorer": str(scorer_path),
        "splits": str(split_dir),
        "num_scorer_records": num_scorer_records,
        "split_counts": split_counts,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
