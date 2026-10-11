from pathlib import Path

import pytest

from source_code.pdf_extractor import extract_pdf


ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "data" / "Sample_Financial_Report_for_Chunking_Screening.pdf"


def test_pagewise_extraction_reads_all_report_pages():
    pages, warnings = extract_pdf(PDF)
    assert len(pages) == 9
    assert pages[2].page_number == 3
    assert "Financial Performance" in pages[2].text
    assert any("Revenue" in table for _, table in pages[2].tables)


def test_pdf_artifact_bullets_are_normalized_without_losing_items():
    pages, _ = extract_pdf(PDF)
    assert "(cid:127)" not in pages[1].text
    assert "• Revenue increased by 24.6%" in pages[1].text


def test_missing_input_raises_actionable_error():
    with pytest.raises(FileNotFoundError, match="does not exist"):
        extract_pdf(ROOT / "data" / "missing.pdf")
