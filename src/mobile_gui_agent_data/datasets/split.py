import hashlib
from collections import defaultdict
from collections.abc import Iterable

from mobile_gui_agent_data.schemas import StepSample


def normalize_instruction(instruction: str) -> str:
    return " ".join(instruction.strip().lower().split())


def instruction_hash(instruction: str) -> int:
    digest = hashlib.md5(normalize_instruction(instruction).encode("utf-8")).hexdigest()
    return int(digest, 16)


def instruction_wise_split(
    steps: Iterable[StepSample],
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
) -> dict[str, list[StepSample]]:
    grouped: dict[str, list[StepSample]] = defaultdict(list)
    for step in steps:
        grouped[normalize_instruction(step.task)].append(step)

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
