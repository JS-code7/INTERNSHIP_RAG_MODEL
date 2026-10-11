# ArgyleEnigma AI ML Intern Assignment

## Objective

This project extracts a financial PDF page by page and turns its headings, prose, lists, tables, and long clauses into retrieval-ready JSONL chunks. It is designed for local RAG preparation and requires no API key, vector database, GPU, or network connection at runtime.

## Features

- One-based physical page metadata and deterministic chunk IDs.
- Coordinate-ordered heading and table mapping, including numbered, named, and appendix headings.
- Conservative boilerplate removal, table extraction as Markdown, and no duplicated table text.
- Recursive paragraph/sentence splitting with natural-boundary overlap.
- Token counts using `tiktoken` when installed, otherwise a documented deterministic estimate.
- JSONL, representative JSON, factual run summary, and automated validation.

## Layout

```text
ArgyleEnigma_AI_ML_Intern_Assignment/
  README.md
  requirements.txt
  technical_explanation.pdf
  data/Sample_Financial_Report_for_Chunking_Screening.pdf
  source_code/
  output/
  tests/
```

## Windows setup and execution

From the project root:

```powershell
python -m pip install -r requirements.txt
python -m source_code.chunker --input data/Sample_Financial_Report_for_Chunking_Screening.pdf --output output/chunks.jsonl --representative-output output/representative_chunks.json --summary-output output/chunking_summary.json --target-tokens 400 --overlap-tokens 60
python -m pytest -q
```

The `--target-tokens`, `--overlap-tokens`, and `--max-tokens` options are configurable. The supplied report is short, so the default 400-token target is automatically reduced modestly to 260 tokens only when needed to avoid fewer than ten meaningful chunks. The effective parameters are recorded in `output/chunking_summary.json`.

## Outputs

- `chunks.jsonl`: one independently parseable chunk record per line.
- `representative_chunks.json`: ten or more distinct records selected from the full output.
- `chunking_summary.json`: input facts, effective configuration, coverage, warnings, and validation results.

Each record includes `chunk_id`, `document_id`, `document_name`, `page_number`, `page_numbers`, `section`, `section_path`, `chunk_index`, `content_type`, `text`, `token_count`, `token_count_method`, and `overlap_tokens`.

## Design decisions and limitations

The extractor uses `pypdf` for page validation and `pdfplumber` for coordinate-aware text lines and tables. Lines belonging to detected table bounding boxes are removed from the prose path, avoiding the common duplicate-table problem. Tables are emitted in reading order, so each inherits the heading context that precedes its own bounding box. Tables use Markdown with headers retained. Headings are carried with their content and long clauses split at sentence boundaries before a word-level fallback. The configured 60-token overlap is available when a logical unit must be split; this report's structural chunks stayed below the target, so the executed run inserted zero actual overlap. Metadata is non-zero only when the exact sentence tail was inserted; independent table chunks report zero.

PDF layout is inherently heuristic: multi-column pages, image-only scans, unusual font encodings, merged cells, and decorative headings may need page-specific rules or OCR. The pipeline reports extraction warnings instead of inventing missing data. Production systems could add OCR fallback, layout models, page coordinates, semantic embeddings, cross-page table stitching, and human review sampling.
