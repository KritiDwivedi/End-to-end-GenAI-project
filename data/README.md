# Data

Local data artifacts for development live here.

- `downloads/` holds raw source files fetched from SEC EDGAR, grouped by year.
- Downloaded payloads are gitignored because the corpus can get large.
- Fetch a sample corpus with `uv run data/download.py`
- Convert downloaded HTML filings to Markdown with `uv run data/html_to_markdown.py`
- Build Docling chunks and Supabase embeddings with `uv run data/build_document_chunks.py --smoke`
- Ingestion progress is shown in the terminal and written to `data/markdown/ingestion.log`.
- Use `--log-file path/to/run.log` to choose a different log location.

The chunk builder uses local MiniLM inference. `--batch-size` controls how many texts are encoded together; it does not create remote API calls. Database writes remain ordered and idempotent so a failed run can be inspected and rerun safely.
