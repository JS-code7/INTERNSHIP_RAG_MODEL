import json
from pathlib import Path

from source_code.chunker import run_pipeline
from source_code.validators import validate_records


ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "data" / "Sample_Financial_Report_for_Chunking_Screening.pdf"


def test_full_pipeline_generates_valid_distinct_outputs(tmp_path: Path):
    summary = run_pipeline(PDF, tmp_path / "chunks.jsonl", tmp_path / "representative.json", tmp_path / "summary.json", 400, 60, 550)
    records = [json.loads(line) for line in (tmp_path / "chunks.jsonl").read_text(encoding="utf-8").splitlines()]
    reps = json.loads((tmp_path / "representative.json").read_text(encoding="utf-8"))
    assert summary["total_pages_processed"] == 9
    assert summary["validation"]["records_valid"]
    assert len(records) >= 10 and len(reps) >= 10
    assert not validate_records(records, 9)
    assert len({record["chunk_id"] for record in records}) == len(records)
    joined_sections = " ".join(record["section"] for record in records)
    for expected in ["Financial", "Risk", "Sustainability", "Compliance"]:
        assert expected in joined_sections
    assert all(1 <= record["page_number"] <= 9 for record in records)
    assert any("1,842.6" in record["text"] for record in records)
    assert any("1,086" in record["text"] for record in records)
    assert any("Credit Risk" in record["text"] for record in records)
    assert any("Employee compliance training completion" in record["text"] for record in records)


def test_real_report_table_sections_and_heading_recognition(tmp_path: Path):
    run_pipeline(PDF, tmp_path / "chunks.jsonl", tmp_path / "representative.json", tmp_path / "summary.json")
    records = [json.loads(line) for line in (tmp_path / "chunks.jsonl").read_text(encoding="utf-8").splitlines()]
    table_sections = {(record["page_number"], record["section"]) for record in records if record["content_type"] == "table"}
    assert (3, "2 Financial Performance > 2.1 Consolidated Results") in table_sections
    assert (3, "2 Financial Performance > 2.2 Segment Performance") in table_sections
    assert (4, "3 Risk Management > 3.1 Principal Risk Categories") in table_sections
    assert (5, "4 Corporate Governance > 4.1 Board Structure") in table_sections
    assert (6, "5 Sustainability and ESG > 5.1 Environmental Performance") in table_sections
    assert (7, "6 Regulatory and Compliance Disclosures > Compliance Metrics") in table_sections
    assert (8, "7 Management Outlook > Selected FY2026-27 Targets") in table_sections
    assert (9, "Appendix A - Document Index") in table_sections
    sections = " ".join(record["section"] for record in records)
    for heading in ["Forward-Looking Statement", "Appendix A", "Appendix B", "Selected FY2026-27 Targets"]:
        assert heading in sections
    bullets = [record for record in records if record["content_type"] == "bullet_list"]
    assert any("Revenue increased by 24.6%" in record["text"] for record in bullets)
    assert any("Q1 meeting" in record["text"] for record in bullets)


def test_policy_clauses_keep_labels_and_context_when_flushed(tmp_path: Path):
    run_pipeline(PDF, tmp_path / "chunks.jsonl", tmp_path / "representative.json", tmp_path / "summary.json")
    records = [json.loads(line) for line in (tmp_path / "chunks.jsonl").read_text(encoding="utf-8").splitlines()]
    ai_intro = next(record for record in records if record["page_number"] == 4 and record["section"].endswith("AI and Model Risk") and "The company uses machine-learning models" in record["text"])
    ai_clause = next(record for record in records if record["page_number"] == 4 and record["section"].endswith("AI and Model Risk") and record["text"].startswith("Long-form policy clause:"))
    customer_clause = next(record for record in records if record["page_number"] == 7 and record["section"].endswith("Customer Data Protection Clause"))
    forward_clause = next(record for record in records if record["page_number"] == 8 and record["section"].endswith("Forward-Looking Statement"))
    assert ai_intro["content_type"] == "paragraph"
    assert ai_clause["content_type"] == "policy_clause"
    assert customer_clause["content_type"] == "policy_clause"
    assert forward_clause["content_type"] == "policy_clause"
    assert "Long-form policy clause:" not in ai_intro["text"]


def test_representatives_are_exact_records_and_report_has_zero_actual_overlap(tmp_path: Path):
    summary = run_pipeline(PDF, tmp_path / "chunks.jsonl", tmp_path / "representative.json", tmp_path / "summary.json")
    records = [json.loads(line) for line in (tmp_path / "chunks.jsonl").read_text(encoding="utf-8").splitlines()]
    representatives = json.loads((tmp_path / "representative.json").read_text(encoding="utf-8"))
    by_id = {record["chunk_id"]: record for record in records}
    assert all(by_id[record["chunk_id"]] == record for record in representatives)
    assert summary["overlap"]["chunks_with_actual_overlap"] == 0
    assert summary["overlap"]["actual_overlap_tokens_total"] == 0
    assert all(record["token_count"] <= 550 for record in records)


def test_repeated_runs_have_stable_ids(tmp_path: Path):
    one = run_pipeline(PDF, tmp_path / "one.jsonl", tmp_path / "one.json", tmp_path / "one_summary.json")
    two = run_pipeline(PDF, tmp_path / "two.jsonl", tmp_path / "two.json", tmp_path / "two_summary.json")
    first_ids = [json.loads(line)["chunk_id"] for line in (tmp_path / "one.jsonl").read_text(encoding="utf-8").splitlines()]
    second_ids = [json.loads(line)["chunk_id"] for line in (tmp_path / "two.jsonl").read_text(encoding="utf-8").splitlines()]
    assert one["total_chunks_generated"] == two["total_chunks_generated"]
    assert first_ids == second_ids
