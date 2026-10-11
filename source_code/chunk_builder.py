"""Structure-aware chunk construction and deterministic token accounting."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .structure_parser import Block

SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
WORDS = re.compile(r"\w+|[^\w\s]", re.UNICODE)


class TokenCounter:
    def __init__(self) -> None:
        try:
            import tiktoken
            self._encoder = tiktoken.get_encoding("cl100k_base")
            self.method = "tiktoken_cl100k_base"
        except Exception:
            self._encoder = None
            self.method = "deterministic_regex_estimate"

    def count(self, text: str) -> int:
        return len(self._encoder.encode(text)) if self._encoder else len(WORDS.findall(text))


@dataclass(frozen=True)
class ChunkDraft:
    page_number: int
    page_numbers: list[int]
    section_path: str
    content_type: str
    text: str
    overlap_tokens: int


def _split_text(text: str, counter: TokenCounter, maximum: int) -> list[str]:
    if counter.count(text) <= maximum:
        return [text]
    sentences = SENTENCE.split(text)
    if len(sentences) == 1:
        words = text.split()
        return [" ".join(words[index:index + maximum]) for index in range(0, len(words), maximum)]
    pieces: list[str] = []
    current: list[str] = []
    for sentence in sentences:
        candidate = " ".join(current + [sentence])
        if current and counter.count(candidate) > maximum:
            pieces.append(" ".join(current)); current = [sentence]
        else:
            current.append(sentence)
    if current:
        pieces.append(" ".join(current))
    return pieces


def _overlap_tail(text: str, counter: TokenCounter, budget: int) -> str:
    sentences = SENTENCE.split(text)
    tail: list[str] = []
    for sentence in reversed(sentences):
        candidate = " ".join([sentence] + tail)
        if tail and counter.count(candidate) > budget:
            break
        tail.insert(0, sentence)
    return " ".join(tail)


def build_chunks(blocks: list[Block], target: int, overlap: int, maximum: int) -> tuple[list[ChunkDraft], TokenCounter]:
    counter = TokenCounter()
    drafts: list[ChunkDraft] = []
    current: list[str] = []
    page_numbers: list[int] = []
    current_section = ""
    current_kind = "paragraph"
    current_overlap = 0

    def flush() -> None:
        nonlocal current, page_numbers, current_overlap
        if not current:
            return
        text = "\n\n".join(current).strip()
        drafts.append(ChunkDraft(page_numbers[0], sorted(set(page_numbers)), current_section, current_kind, text, current_overlap))
        current = []; page_numbers = []; current_overlap = 0

    for block in blocks:
        if current and (block.content_type == "table" or block.content_type == "policy_clause" or current_kind == "policy_clause"):
            flush()
        # Prose and clauses aim for the retrieval target; tables remain whole
        # unless they exceed the hard maximum (row splitting is a future extension).
        parts = _split_text(block.text, counter, maximum if block.content_type == "table" else target)
        for part in parts:
            same_section = block.section_path == current_section
            candidate = "\n\n".join(current + [part])
            if current and (not same_section or counter.count(candidate) > target):
                previous_text = "\n\n".join(current)
                flush()
                if same_section and overlap:
                    tail = _overlap_tail(previous_text, counter, overlap)
                    if tail and tail != part and counter.count("\n\n".join([tail, part])) <= maximum:
                        current = [tail]
                        page_numbers = [block.page_number]
                        current_overlap = counter.count(tail)
            if not current:
                current_section = block.section_path
                current_kind = block.content_type
            elif current_kind != block.content_type:
                current_kind = "mixed"
            current.append(part)
            page_numbers.append(block.page_number)
            if counter.count("\n\n".join(current)) >= target:
                flush()
        if block.content_type == "table":
            flush()
    flush()
    # The metadata is assigned only where the exact tail was injected above.
    # Independent table chunks and merely adjacent same-section chunks remain zero.
    return drafts, counter
