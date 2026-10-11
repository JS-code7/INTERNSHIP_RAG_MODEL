from source_code.chunk_builder import build_chunks
from source_code.structure_parser import Block


def test_metadata_context_and_deterministic_chunking():
    blocks = [Block(3, "2. Financial Performance > 2.1 Consolidated Results", "paragraph", "Revenue increased materially. Profit after tax also increased.")]
    first, _ = build_chunks(blocks, 30, 5, 50)
    second, _ = build_chunks(blocks, 30, 5, 50)
    assert first == second
    assert first[0].page_number == 3
    assert "Financial Performance" in first[0].section_path


def test_long_clause_is_not_silently_truncated():
    clause = " ".join(["This policy sentence protects customers."] * 40)
    chunks, counter = build_chunks([Block(7, "6. Regulatory and Compliance Disclosures", "policy_clause", clause)], 35, 5, 45)
    assert len(chunks) > 1
    assert "protects customers" in " ".join(chunk.text for chunk in chunks)
    assert all(counter.count(chunk.text) <= 45 for chunk in chunks)


def test_table_text_survives_as_a_whole_block():
    table = "| Metric | FY2025-26 |\n| --- | --- |\n| Revenue | 1,842.6 |"
    chunks, _ = build_chunks([Block(3, "2. Financial Performance", "table", table)], 100, 0, 120)
    assert chunks[0].content_type == "table"
    assert "Metric" in chunks[0].text and "1,842.6" in chunks[0].text


def test_overlap_metadata_matches_injected_sentence_tail():
    text = "First sentence establishes context. Second sentence supplies detail. Third sentence completes the discussion."
    chunks, counter = build_chunks([Block(1, "Section", "paragraph", text)], 8, 5, 20)
    assert len(chunks) > 1
    assert chunks[1].overlap_tokens > 0
    assert chunks[1].overlap_tokens <= 5
    assert chunks[1].text.startswith("First sentence establishes context.")
    assert all(counter.count(chunk.text) <= 20 for chunk in chunks)


def test_independent_table_chunks_do_not_claim_overlap():
    blocks = [Block(3, "Section", "table", "| A |\n| --- |\n| 1 |"), Block(3, "Section", "table", "| B |\n| --- |\n| 2 |")] 
    chunks, _ = build_chunks(blocks, 100, 20, 120)
    assert [chunk.overlap_tokens for chunk in chunks] == [0, 0]
