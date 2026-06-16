from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable, List, Sequence


def load_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, records: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(json.dumps(record, ensure_ascii=False) for record in records)
    if content:
        content += "\n"
    path.write_text(content, encoding="utf-8")


def write_csv(path: Path, records: Iterable[dict]) -> None:
    rows = list(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8", newline="")
        return

    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def upsert_records(existing: Iterable[dict], incoming: Iterable[dict], key_fields: Sequence[str]) -> List[dict]:
    merged: dict[tuple, dict] = {}
    ordered_keys: list[tuple] = []

    for record in existing:
        key = tuple(record.get(field) for field in key_fields)
        if key not in merged:
            ordered_keys.append(key)
        merged[key] = record

    for record in incoming:
        key = tuple(record.get(field) for field in key_fields)
        if key not in merged:
            ordered_keys.append(key)
        merged[key] = record

    return [merged[key] for key in ordered_keys]
