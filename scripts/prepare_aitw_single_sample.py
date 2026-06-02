import argparse
import json
from pathlib import Path
from typing import Any

from datasets import load_dataset
from PIL import Image

from mobile_gui_agent_data.pipelines.aitw_single import reprocess_aitw_single_raw


def to_jsonable(value: Any, image_dir: Path | None, row_idx: int, field_name: str) -> Any:
    if isinstance(value, Image.Image):
        if image_dir is None:
            return {"type": "PIL.Image", "size": list(value.size), "mode": value.mode}
        image_dir.mkdir(parents=True, exist_ok=True)
        path = image_dir / f"{row_idx:06d}_{field_name}.png"
        value.save(path)
        return {"path": str(path), "size": list(value.size), "mode": value.mode}
    if isinstance(value, dict):
        return {key: to_jsonable(item, image_dir, row_idx, key) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item, image_dir, row_idx, field_name) for item in value]
    if hasattr(value, "tolist"):
        return value.tolist()
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="cjfcsjt/AITW_Single")
    parser.add_argument("--subset", default="unseen_subject", choices=["unseen_subject", "unseen_verb"])
    parser.add_argument("--split", default="train", choices=["train", "validation", "test"])
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--root", default=".")
    parser.add_argument("--no-images", action="store_true")
    parser.add_argument("--qdd-samples", type=int, default=200)
    args = parser.parse_args()

    root = Path(args.root)
    tag = f"{args.subset}_{args.split}_{args.limit}"
    raw_dir = root / "data" / "raw" / "aitw_single"
    interim_dir = root / "data" / "interim" / "aitw_single"
    processed_dir = root / "data" / "processed" / "aitw_single"
    preference_dir = root / "data" / "preferences" / "aitw_single"
    report_dir = root / "reports" / "aitw_single"

    image_dir = None if args.no_images else raw_dir / f"images_{tag}"
    raw_suffix = "" if args.no_images else "_with_images"
    raw_path = raw_dir / f"{tag}{raw_suffix}.jsonl"
    for directory in [raw_dir, interim_dir, processed_dir, preference_dir, report_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    dataset = load_dataset(args.dataset, args.subset, split=args.split, streaming=True)
    with raw_path.open("w", encoding="utf-8") as f:
        for idx, row in enumerate(dataset.take(args.limit)):
            payload = {
                key: to_jsonable(value, image_dir, idx, key)
                for key, value in row.items()
            }
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    result = reprocess_aitw_single_raw(
        raw_path=raw_path,
        tag=tag,
        qdd_samples=args.qdd_samples,
        root=root,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
