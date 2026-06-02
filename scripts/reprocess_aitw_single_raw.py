import argparse
import json
from pathlib import Path

from mobile_gui_agent_data.pipelines.aitw_single import reprocess_aitw_single_raw


def infer_tag(raw_path: str) -> str:
    name = Path(raw_path).name
    for suffix in ["_with_images.jsonl", ".jsonl", ".json"]:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return Path(raw_path).stem


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", required=True)
    parser.add_argument("--tag", default=None)
    parser.add_argument("--qdd-samples", type=int, default=200)
    parser.add_argument("--root", default=".")
    args = parser.parse_args()

    tag = args.tag or infer_tag(args.raw)
    result = reprocess_aitw_single_raw(
        raw_path=args.raw,
        tag=tag,
        qdd_samples=args.qdd_samples,
        root=args.root,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
