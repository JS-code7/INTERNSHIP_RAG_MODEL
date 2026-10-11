"""Page-aware extraction with optional table detection."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import re

from pypdf import PdfReader


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text: str
    tables: list[tuple[float, str]] = field(default_factory=list)
    lines: list[tuple[float, str]] = field(default_factory=list)


def _markdown_table(table: list[list[str | None]]) -> str:
    rows = [[("" if cell is None else " ".join(cell.split())) for cell in row] for row in table]
    rows = [row for row in rows if any(row)]
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    header = rows[0]
    return "\n".join([
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * width) + " |",
        *["| " + " | ".join(row) + " |" for row in rows[1:]],
    ])


def extract_pdf(pdf_path: Path) -> tuple[list[ExtractedPage], list[str]]:
    """Extract all readable pages and tables, retaining physical page numbers."""
    if not pdf_path.exists() or not pdf_path.is_file():
        raise FileNotFoundError(f"PDF input does not exist: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a PDF file, received: {pdf_path.name}")
    warnings: list[str] = []
    try:
        reader = PdfReader(str(pdf_path))
    except Exception as exc:
        raise ValueError(f"Could not read PDF: {exc}") from exc
    if not reader.pages:
        raise ValueError("PDF contains no pages")
    tables_by_page: dict[int, list[tuple[float, str]]] = {}
    prose_by_page: dict[int, list[tuple[float, str]]] = {}
    try:
        import pdfplumber  # optional enhancement; pypdf remains the text authority
        with pdfplumber.open(str(pdf_path)) as document:
            for index, page in enumerate(document.pages, start=1):
                found_tables = page.find_tables()
                tables_by_page[index] = [(table.bbox[1], markdown) for table in found_tables if (markdown := _markdown_table(table.extract()))]
                # Exclude characters inside recognized table boxes from prose so table
                # cells are represented exactly once, in their Markdown block.
                boxes = [table.bbox for table in found_tables]
                def outside_table(obj: dict[str, Any]) -> bool:
                    if obj.get("object_type") != "char":
                        return True
                    x_mid = (obj["x0"] + obj["x1"]) / 2
                    y_mid = (obj["top"] + obj["bottom"]) / 2
                    return not any(x0 <= x_mid <= x1 and top <= y_mid <= bottom for x0, top, x1, bottom in boxes)
                prose_by_page[index] = [(line["top"], line["text"]) for line in page.filter(outside_table).extract_text_lines(strip=True)]
    except Exception as exc:
        warnings.append(f"Table extraction unavailable or incomplete: {exc}")
    pages: list[ExtractedPage] = []
    for number, page in enumerate(reader.pages, start=1):
        lines = prose_by_page.get(number)
        if lines is None:
            lines = [(float(index), line) for index, line in enumerate((page.extract_text(extraction_mode="layout") or "").splitlines())]
        cleaned: list[tuple[float, str]] = []
        for top, raw in lines:
            line = raw.replace("\x7f", "•")
            line = re.sub(r"\(cid:127\)", "•", line)
            line = re.sub(r"Aurelia Digital Finance Ltd\. — Fictional Screening Dataset\s*Page\s*\d+", "", line)
            line = " ".join(line.split())
            if line:
                cleaned.append((top, line))
        text = "\n".join(line for _, line in cleaned)
        if not text:
            warnings.append(f"Page {number} yielded no selectable text.")
        pages.append(ExtractedPage(number, text, tables_by_page.get(number, []), cleaned))
    return pages, warnings
