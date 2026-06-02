import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

import yaml


def read_jsonl(path: str | Path) -> Iterator[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def read_records(path: str | Path) -> Iterator[dict[str, Any]]:
    """Read records from either JSONL or JSON.

    JSON input may be a single object, a list of objects, or an object with an
    ``episodes`` list. This keeps early dataset adapters easy to test before
    committing to one raw-data layout.
    """
    input_path = Path(path)
    if input_path.suffix.lower() == ".jsonl":
        yield from read_jsonl(input_path)
        return

    with input_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    if isinstance(payload, list):
        yield from payload
    elif isinstance(payload, dict) and isinstance(payload.get("episodes"), list):
        yield from payload["episodes"]
    elif isinstance(payload, dict):
        yield payload
    else:
        raise ValueError(f"Unsupported JSON payload in {input_path}")


def write_jsonl(path: str | Path, records: Iterable[dict[str, Any]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)
