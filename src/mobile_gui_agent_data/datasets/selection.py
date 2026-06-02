from collections import Counter, defaultdict
from typing import Any


QUALITY_ORDER = {"low": 0, "medium": 1, "high": 2}


def step_key(record: dict[str, Any]) -> str:
    return f"{record.get('episode_id', 'unknown')}:{record.get('step_id', 0)}"


def quality_bucket(record: dict[str, Any]) -> str:
    audit = record.get("audit") or {}
    return audit.get("quality_bucket", "low")


def difficulty_score(record: dict[str, Any]) -> float:
    metadata = record.get("metadata") or {}
    audit = record.get("audit") or {}
    if "difficulty_score" in metadata:
        return float(metadata["difficulty_score"])
    if "model_error_rate" in metadata:
        return float(metadata["model_error_rate"])
    # Lower rule quality can be useful for inspection, but QDD selection should
    # prefer clean samples unless the caller lowers the quality threshold.
    return 1.0 - float(audit.get("quality_score", 1.0))


def action_type(record: dict[str, Any]) -> str:
    action = record.get("action") or {}
    return str(action.get("type", "unknown"))


def select_quality_difficulty_diversity(
    records: list[dict[str, Any]],
    max_samples: int,
    min_quality: str = "high",
    per_action_limit: int | None = None,
) -> list[dict[str, Any]]:
    min_quality_value = QUALITY_ORDER[min_quality]
    candidates = [
        record
        for record in records
        if QUALITY_ORDER.get(quality_bucket(record), -1) >= min_quality_value
    ]
    candidates.sort(key=lambda record: (difficulty_score(record), step_key(record)), reverse=True)

    selected = []
    selected_counts = Counter()
    by_action: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in candidates:
        by_action[action_type(record)].append(record)

    while len(selected) < max_samples:
        progressed = False
        for current_action in sorted(by_action):
            if len(selected) >= max_samples:
                break
            if per_action_limit is not None and selected_counts[current_action] >= per_action_limit:
                continue
            if not by_action[current_action]:
                continue
            selected.append(by_action[current_action].pop(0))
            selected_counts[current_action] += 1
            progressed = True
        if not progressed:
            break

    return selected
