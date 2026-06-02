from collections import Counter
from pathlib import Path
from typing import Any


def summarize_scorer_records(records: list[dict[str, Any]], image_root: str | Path | None = None) -> dict:
    labels = Counter(str(record.get("label", "")) for record in records)
    negative_types = Counter(
        str(record.get("negative_type", ""))
        for record in records
        if str(record.get("label", "")) == "No"
    )
    action_types = Counter(
        str((record.get("candidate_action") or {}).get("type", "unknown"))
        for record in records
    )
    instructions = {str(record.get("instruction", "")).strip().lower() for record in records}
    episodes = {str(record.get("episode_id", "")) for record in records}
    images = [record.get("image") for record in records if record.get("image")]

    image_root_path = Path(image_root) if image_root else None
    missing_images = 0
    if image_root_path is not None:
        for image in images:
            image_path = Path(str(image))
            if not image_path.is_absolute():
                image_path = image_root_path / image_path
            missing_images += int(not image_path.exists())

    return {
        "num_records": len(records),
        "num_unique_instructions": len(instructions),
        "num_unique_episodes": len(episodes),
        "labels": dict(labels.most_common()),
        "negative_types": dict(negative_types.most_common()),
        "candidate_action_types": dict(action_types.most_common()),
        "num_images": len(images),
        "missing_images": missing_images if image_root_path is not None else None,
    }
