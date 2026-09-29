"""Tiny helpers for reading and writing JSONL (one JSON object per line)."""

import json
from collections.abc import Iterable
from pathlib import Path


def read_jsonl(path: str | Path) -> list[dict]:
    # Always pass encoding: Windows defaults to cp1252, which breaks on "₹".
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(records: Iterable[dict], path: str | Path) -> int:
    """Write records to path (creating parent folders) and return how many were written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for record in records:
            # ensure_ascii=False keeps "₹" readable instead of "₹".
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count
