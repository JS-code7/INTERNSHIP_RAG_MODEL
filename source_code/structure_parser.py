"""Lightweight structural interpretation of extracted PDF pages."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .pdf_extractor import ExtractedPage

HEADING = re.compile(r"^(?:(\d{1,2}(?:\.\d+)*)\.?\s+(.+)|(Appendix [A-Z]\s+[—-]\s+.+))$")
NAMED_HEADINGS = {"Key Highlights", "Reporting Boundary", "Board Meeting Disclosure", "Customer Data Protection Clause", "Compliance Metrics", "Selected FY2026-27 Targets", "Forward-Looking Statement"}
ROOT_NAMED_HEADINGS = {"End of Document"}
BOILERPLATE = re.compile(r"^(Aurelia Digital Finance Ltd\. — Fictional Screening Dataset|Page \d+)$")


@dataclass(frozen=True)
class Block:
    page_number: int
    section_path: str
    content_type: str
    text: str


def _is_heading(line: str) -> tuple[bool, int, str]:
    normalized = " ".join(line.replace("–", "-").replace("—", "-").split())
    if normalized in ROOT_NAMED_HEADINGS:
        return True, 1, normalized
    if normalized in NAMED_HEADINGS:
        return True, 0, normalized
    match = HEADING.match(normalized)
    if not match:
        return False, 0, ""
    if match.group(1):
        return True, match.group(1).count(".") + 1, f"{match.group(1)} {match.group(2)}"
    return True, 1, match.group(3)


def _paragraphs(lines: list[str]) -> list[str]:
    """Join wrapped source lines while retaining bullets as a single list block."""
    result: list[str] = []
    buffer: list[str] = []
    for line in lines:
        bullet = line.lstrip().startswith(("•", "-", ""))
        if bullet:
            if buffer:
                result.append(" ".join(buffer)); buffer = []
            result.append("- " + line.lstrip("•- ").strip())
        else:
            buffer.append(line.strip())
    if buffer:
        result.append(" ".join(buffer))
    return result


def classify_paragraph(text: str, section_path: str) -> str:
    """Apply one policy classification rule at every paragraph flush point."""
    normalized = text.strip()
    if normalized.startswith("- "):
        return "bullet_list"
    policy_starts = ("Long-form policy clause:", "Customer information shall", "Statements concerning future")
    policy_sections = ("Customer Data Protection Clause", "Forward-Looking Statement")
    if normalized.startswith(policy_starts) or section_path.endswith(policy_sections):
        return "policy_clause"
    return "paragraph"


def parse_structure(pages: list[ExtractedPage]) -> list[Block]:
    path: dict[int, str] = {}
    blocks: list[Block] = []
    for page in pages:
        events = [(top, "line", line) for top, line in page.lines if not BOILERPLATE.match(line)]
        events.extend((top, "table", table) for top, table in page.tables)
        events.sort(key=lambda event: event[0])
        current: list[str] = []
        last_line_top: float | None = None

        def emit_current() -> None:
            nonlocal current
            section = " > ".join(path.values()) or "Document"
            for paragraph in _paragraphs(current):
                blocks.append(Block(page.page_number, section, classify_paragraph(paragraph, section), paragraph))
            current = []

        for top, event_type, value in events:
            if event_type == "table":
                emit_current()
                blocks.append(Block(page.page_number, " > ".join(path.values()) or "Document", "table", value))
                last_line_top = None
                continue
            line = value
            # PDF line positions provide a dependable paragraph break when the
            # vertical gap is materially larger than ordinary wrapped leading.
            if current and last_line_top is not None and top - last_line_top > 16:
                emit_current()
            found, level, title = _is_heading(line)
            if found:
                emit_current()
                if level == 0:  # named subheading: retain the surrounding numbered section
                    level = 2 if 1 in path else 1
                path[level] = " ".join(title.split())
                for deeper in [key for key in path if key > level]:
                    del path[deeper]
                last_line_top = None
                continue
            if line.startswith("Long-form policy clause:") and current:
                emit_current()
            current.append(line)
            last_line_top = top
        emit_current()
    return [block for block in blocks if block.text.strip()]
