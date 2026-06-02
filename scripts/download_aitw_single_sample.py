import argparse
import json
from pathlib import Path
from typing import Any

from datasets import load_dataset
from PIL import Image


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
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--output", required=True)
    parser.add_argument("--image-dir", default=None, help="Optional directory to save decoded images")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image_dir = Path(args.image_dir) if args.image_dir else None

    dataset = load_dataset(args.dataset, args.subset, split=args.split, streaming=True)

    with output_path.open("w", encoding="utf-8") as f:
        for idx, row in enumerate(dataset.take(args.limit)):
            payload = {
                key: to_jsonable(value, image_dir, idx, key)
                for key, value in row.items()
            }
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
