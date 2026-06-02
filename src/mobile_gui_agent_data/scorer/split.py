import hashlib
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from mobile_gui_agent_data.datasets.split import normalize_instruction


def instruction_hash(instruction: str) -> int:
    digest = hashlib.md5(normalize_instruction(instruction).encode("utf-8")).hexdigest()
    return int(digest, 16)


def instruction_wise_split_records(
    records: Iterable[dict[str, Any]],
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        instruction = normalize_instruction(str(record.get("instruction", "")))
        grouped[instruction].append(record)

    splits = {"train": [], "val": [], "test": []}
    train_cutoff = int(train_ratio * 10_000)
    val_cutoff = int((train_ratio + val_ratio) * 10_000)

    for instruction, group in grouped.items():
        bucket = instruction_hash(instruction) % 10_000
        if bucket < train_cutoff:
            splits["train"].extend(group)
        elif bucket < val_cutoff:
            splits["val"].extend(group)
        else:
            splits["test"].extend(group)

    return splits
