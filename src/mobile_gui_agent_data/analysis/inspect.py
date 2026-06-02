from collections import Counter, defaultdict
from collections.abc import Iterable
from typing import Any


def value_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return type(value).__name__


def walk_paths(value: Any, prefix: str = "", max_list_items: int = 3) -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            yield path, value_type(child)
            yield from walk_paths(child, path, max_list_items=max_list_items)
    elif isinstance(value, list):
        yield prefix, "list"
        for idx, child in enumerate(value[:max_list_items]):
            path = f"{prefix}[]"
            yield path, value_type(child)
            yield from walk_paths(child, path, max_list_items=max_list_items)


def inspect_records(records: Iterable[dict[str, Any]], limit: int = 20) -> dict[str, Any]:
    path_types: dict[str, Counter] = defaultdict(Counter)
    top_level_keys = Counter()
    action_like_values = Counter()
    num_records = 0

    for record in records:
        num_records += 1
        if num_records > limit:
            break
        top_level_keys.update(record.keys())
        for path, type_name in walk_paths(record):
            path_types[path][type_name] += 1
            lower_path = path.lower()
            if lower_path.endswith("action") or "action_type" in lower_path or lower_path.endswith("operation"):
                value = get_path_sample(record, path)
                if isinstance(value, str):
                    action_like_values[value[:120]] += 1
                elif isinstance(value, dict):
                    raw_type = value.get("type") or value.get("action_type") or value.get("action")
                    if raw_type is not None:
                        action_like_values[str(raw_type)[:120]] += 1

    return {
        "num_records_inspected": min(num_records, limit),
        "top_level_keys": dict(top_level_keys.most_common()),
        "paths": {
            path: dict(counter.most_common())
            for path, counter in sorted(path_types.items(), key=lambda item: item[0])
        },
        "action_like_values": dict(action_like_values.most_common(20)),
    }


def get_path_sample(record: dict[str, Any], path: str) -> Any:
    current: Any = record
    for part in path.split("."):
        if part.endswith("[]"):
            part = part[:-2]
            current = current.get(part) if isinstance(current, dict) else None
            if isinstance(current, list) and current:
                current = current[0]
            else:
                return None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current
