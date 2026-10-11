"""Output validation kept separate from chunk generation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REQUIRED = {"chunk_id", "document_name", "page_number", "section", "chunk_index", "text"}


def validate_records(records: list[dict[str, Any]], page_count: int) -> list[str]:
    errors: list[str] = []
    identifiers: set[str] = set()
    for record in records:
        missing = REQUIRED - set(record)
        if missing:
            errors.append(f"{record.get('chunk_id', '<unknown>')} missing {sorted(missing)}")
        if not isinstance(record.get("text"), str) or not record.get("text", "").strip():
            errors.append(f"{record.get('chunk_id', '<unknown>')} has empty text")
        if record.get("chunk_id") in identifiers:
            errors.append(f"Duplicate chunk_id: {record.get('chunk_id')}")
        identifiers.add(record.get("chunk_id"))
        if not isinstance(record.get("page_number"), int) or not 1 <= record["page_number"] <= page_count:
            errors.append(f"Invalid page number for {record.get('chunk_id', '<unknown>')}")
    return errors


def validate_jsonl(path: Path, page_count: int) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            errors.append(f"JSONL line {line_number}: {exc}")
    return records, errors + validate_records(records, page_count)
