"""CLI entry point for the reproducible local chunking pipeline."""
from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any

from .chunk_builder import build_chunks
from .pdf_extractor import extract_pdf
from .structure_parser import parse_structure
from .validators import validate_jsonl, validate_records

LOG = logging.getLogger(__name__)


def run_pipeline(input_path: Path, output_path: Path, representative_path: Path, summary_path: Path, target_tokens: int = 400, overlap_tokens: int = 60, max_tokens: int = 550) -> dict[str, Any]:
    if target_tokens <= 0 or overlap_tokens < 0 or max_tokens < target_tokens:
        raise ValueError("Require positive target, non-negative overlap, and max >= target.")
    pages, warnings = extract_pdf(input_path)
    blocks = parse_structure(pages)
    effective_target = target_tokens
    drafts, counter = build_chunks(blocks, effective_target, overlap_tokens, max_tokens)
    if len(drafts) < 10 and target_tokens >= 300:
        effective_target = 260
        drafts, counter = build_chunks(blocks, effective_target, overlap_tokens, max_tokens)
        warnings.append("Target reduced to 260 tokens to improve retrieval granularity for this short report.")
    document_id = "aurelia_financial_report_2025_26"
    records = [{
        "chunk_id": f"doc_001_chunk_{index:04d}", "document_id": document_id,
        "document_name": input_path.name, "page_number": draft.page_number,
        "page_numbers": draft.page_numbers, "section": draft.section_path,
        "section_path": draft.section_path.split(" > "), "chunk_index": index,
        "content_type": draft.content_type, "text": draft.text,
        "token_count": counter.count(draft.text), "token_count_method": counter.method,
        "overlap_tokens": draft.overlap_tokens,
    } for index, draft in enumerate(drafts, start=1)]
    validation_errors = validate_records(records, len(pages))
    if validation_errors:
        raise ValueError("Generated records failed validation: " + "; ".join(validation_errors))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records), encoding="utf-8")
    coverage_terms = ["Financial", "Risk", "Governance", "Sustainability", "Compliance", "Outlook", "Appendix"]
    representatives: list[dict[str, Any]] = []
    used: set[str] = set()
    for term in coverage_terms:
        for record in records:
            if term.lower() in record["section"].lower() and record["chunk_id"] not in used:
                representatives.append(record); used.add(record["chunk_id"]); break
    for record in records:
        if len(representatives) >= min(10, len(records)):
            break
        if record["chunk_id"] not in used:
            representatives.append(record); used.add(record["chunk_id"])
    representative_path.parent.mkdir(parents=True, exist_ok=True)
    representative_path.write_text(json.dumps(representatives, ensure_ascii=False, indent=2), encoding="utf-8")
    reread_records, jsonl_errors = validate_jsonl(output_path, len(pages))
    summary = {
        "input_filename": input_path.name, "total_pages_processed": len(pages),
        "total_chunks_generated": len(records), "representative_chunks_selected": len(representatives),
        "parameters": {"requested_target_tokens": target_tokens, "effective_target_tokens": effective_target, "overlap_tokens": overlap_tokens, "max_tokens": max_tokens},
        "token_counting_method": counter.method, "section_coverage": sorted({record["section"] for record in records}),
        "content_type_coverage": dict(Counter(record["content_type"] for record in records)),
        "overlap": {"configured_preferred_tokens": overlap_tokens, "chunks_with_actual_overlap": sum(record["overlap_tokens"] > 0 for record in records), "actual_overlap_tokens_total": sum(record["overlap_tokens"] for record in records), "note": "No overlap was inserted when structural boundaries produced complete chunks below the target."},
        "extraction_warnings": warnings, "validation": {"records_valid": not validation_errors and not jsonl_errors, "jsonl_records_reparsed": len(reread_records), "errors": validation_errors + jsonl_errors},
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Create retrieval-ready chunks from a financial PDF.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--representative-output", required=True, type=Path)
    parser.add_argument("--summary-output", required=True, type=Path)
    parser.add_argument("--target-tokens", type=int, default=400)
    parser.add_argument("--overlap-tokens", type=int, default=60)
    parser.add_argument("--max-tokens", type=int, default=550)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    summary = run_pipeline(args.input, args.output, args.representative_output, args.summary_output, args.target_tokens, args.overlap_tokens, args.max_tokens)
    LOG.info("Processed %s pages into %s chunks.", summary["total_pages_processed"], summary["total_chunks_generated"])


if __name__ == "__main__":
    main()
