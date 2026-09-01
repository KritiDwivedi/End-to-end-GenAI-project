# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "docling",
#   "sentence-transformers",
#   "psycopg[binary]",
#   "pgvector",
#   "tiktoken",
# ]
# ///
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import uuid
from dataclasses import dataclass, asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Iterable

import psycopg
import tiktoken
from docling.chunking import HybridChunker
from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter
from pgvector.psycopg import register_vector
from psycopg.types.json import Jsonb
from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer
from sentence_transformers import SentenceTransformer


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
BACKEND_ENV_FILE = PROJECT_DIR / "backend" / ".env"
DOWNLOADS_MANIFEST = BASE_DIR / "downloads" / "manifest.json"
MARKDOWN_DIR = BASE_DIR / "markdown"
OUTPUT_MANIFEST = MARKDOWN_DIR / "chunk_manifest.json"
DEFAULT_LOG_FILE = MARKDOWN_DIR / "ingestion.log"

EMBEDDING_MODEL_DEFAULT = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSIONS_DEFAULT = 384
EMBEDDING_TOKEN_LIMIT_DEFAULT = 256
CHUNK_BATCH_SIZE_DEFAULT = 32
SMOKE_FILE_COUNT_DEFAULT = 1
SMOKE_CHUNK_COUNT_DEFAULT = 1

COMPANY_NAME_BY_TICKER = {
    "AAPL": "Apple",
    "AMZN": "Amazon",
    "GOOGL": "Alphabet",
    "MSFT": "Microsoft",
    "NVDA": "NVIDIA",
}


@dataclass(slots=True)
class ChunkRecord:
    year: str
    ticker: str
    accession_number: str
    markdown_path: str
    chunk_index: int
    token_count: int
    status: str


logger = logging.getLogger("document_chunks")


def configure_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)


def load_env_value(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    if BACKEND_ENV_FILE.exists():
        for line in BACKEND_ENV_FILE.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, raw_value = stripped.split("=", 1)
            if key.strip() == name:
                return raw_value.strip().strip('"').strip("'")
    return default


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_download_manifest() -> dict[str, dict[str, Any]]:
    if not DOWNLOADS_MANIFEST.exists():
        return {}
    manifest = load_json(DOWNLOADS_MANIFEST)
    lookup: dict[str, dict[str, Any]] = {}
    for item in manifest.get("filings", []):
        lookup[item["local_path"]] = item
    return lookup


def parse_filename(path: Path) -> dict[str, str]:
    stem = path.stem
    ticker, form, filing_date, accession_number = stem.split("_", 3)
    return {
        "ticker": ticker.upper(),
        "form": form.upper(),
        "filing_date": filing_date,
        "accession_number": accession_number,
    }


def iter_markdown_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.md") if path.is_file())


def infer_company_name(ticker: str) -> str:
    return COMPANY_NAME_BY_TICKER.get(ticker.upper(), ticker.upper())


def get_database_url() -> str:
    database_url = load_env_value("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required in the environment or backend/.env")
    return database_url


def get_embedding_model() -> str:
    return load_env_value("LOCAL_EMBEDDING_MODEL", EMBEDDING_MODEL_DEFAULT) or EMBEDDING_MODEL_DEFAULT


def get_embedding_dimensions() -> int:
    raw = load_env_value("LOCAL_EMBEDDING_DIMENSIONS", str(EMBEDDING_DIMENSIONS_DEFAULT))
    return int(raw or EMBEDDING_DIMENSIONS_DEFAULT)


def build_tokenizer(model_name: str, token_limit: int) -> OpenAITokenizer:
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except Exception:  # noqa: BLE001
        encoding = tiktoken.get_encoding("cl100k_base")
    return OpenAITokenizer(tokenizer=encoding, max_tokens=token_limit)


def build_chunker(model_name: str, token_limit: int) -> HybridChunker:
    tokenizer = build_tokenizer(model_name, token_limit)
    return HybridChunker(tokenizer=tokenizer, merge_peers=True)


def load_markdown_as_docling(converter: DocumentConverter, markdown_text: str, source_name: str):
    result = converter.convert_string(
        markdown_text,
        format=InputFormat.MD,
        name=source_name,
    )
    return result.document


def chunk_metadata(chunk: Any) -> dict[str, Any]:
    meta = getattr(chunk, "meta", None)
    if meta is None:
        return {}
    if hasattr(meta, "model_dump"):
        return meta.model_dump(mode="json")
    return dict(meta)


def chunk_section_title(meta: dict[str, Any]) -> str | None:
    headings = meta.get("headings")
    if isinstance(headings, list) and headings:
        first = headings[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            return first.get("text") or first.get("title")
    title = meta.get("title")
    if isinstance(title, str):
        return title
    captions = meta.get("captions")
    if isinstance(captions, list) and captions:
        first = captions[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            return first.get("text") or first.get("title")
    return None


def chunk_page_number(meta: dict[str, Any]) -> int | None:
    for key in ("page_number", "page_no", "page", "pageIndex"):
        value = meta.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def tokenize(text: str, model_name: str) -> int:
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except Exception:  # noqa: BLE001
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def normalize_file_text(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def ensure_markdown_dir() -> None:
    if not MARKDOWN_DIR.exists():
        raise FileNotFoundError(f"Markdown directory not found: {MARKDOWN_DIR}")


def ensure_source_rows(
    connection: psycopg.Connection[Any],
    manifest_lookup: dict[str, dict[str, Any]],
    markdown_path: Path,
    markdown_text: str,
) -> uuid.UUID:
    relative_path = markdown_path.relative_to(MARKDOWN_DIR)
    file_info = parse_filename(markdown_path)
    source_item = manifest_lookup.get(str(relative_path.with_suffix(".htm"))) or manifest_lookup.get(
        str(relative_path.with_suffix(".html"))
    )
    source_url = source_item["source_url"] if source_item else None
    company_name = infer_company_name(file_info["ticker"])
    filing_year = int(file_info["filing_date"][:4])
    metadata = {
        "year": relative_path.parts[0],
        "ticker": file_info["ticker"],
        "form": file_info["form"],
        "filing_date": file_info["filing_date"],
        "accession_number": file_info["accession_number"],
        "source_manifest_path": source_item["local_path"] if source_item else None,
        "source_url": source_url,
    }

    with connection.cursor() as cursor:
        cursor.execute(
            """
            insert into source_documents (
                id,
                company_name,
                ticker,
                cik,
                filing_type,
                filing_date,
                fiscal_year,
                accession_number,
                source_url,
                content_markdown,
                metadata,
                created_at,
                updated_at
            )
            values (
                %(id)s,
                %(company_name)s,
                %(ticker)s,
                %(cik)s,
                %(filing_type)s,
                %(filing_date)s,
                %(fiscal_year)s,
                %(accession_number)s,
                %(source_url)s,
                %(content_markdown)s,
                %(metadata)s,
                now(),
                now()
            )
            on conflict (accession_number) do update set
                company_name = excluded.company_name,
                ticker = excluded.ticker,
                cik = excluded.cik,
                filing_type = excluded.filing_type,
                filing_date = excluded.filing_date,
                fiscal_year = excluded.fiscal_year,
                source_url = excluded.source_url,
                content_markdown = excluded.content_markdown,
                metadata = excluded.metadata,
                updated_at = now()
            returning id
            """,
            {
                "id": uuid.uuid4(),
                "company_name": company_name,
                "ticker": file_info["ticker"],
                "cik": source_item["cik"] if source_item else None,
                "filing_type": file_info["form"],
                "filing_date": date.fromisoformat(file_info["filing_date"]),
                "fiscal_year": filing_year,
                "accession_number": file_info["accession_number"],
                "source_url": source_url,
                "content_markdown": normalize_file_text(markdown_text),
                "metadata": Jsonb(metadata),
            },
        )
        row = cursor.fetchone()
    if row is None:
        raise RuntimeError(f"Could not upsert source_documents row for {relative_path}")
    return row[0]


def chunk_document(
    converter: DocumentConverter,
    chunker: HybridChunker,
    markdown_text: str,
    source_name: str,
) -> list[dict[str, Any]]:
    doc = load_markdown_as_docling(converter, markdown_text, source_name)
    raw_chunks = list(chunker.chunk(doc))
    chunk_rows: list[dict[str, Any]] = []

    for idx, chunk in enumerate(raw_chunks):
        contextual_text = chunker.contextualize(chunk=chunk)
        meta = chunk_metadata(chunk)
        chunk_rows.append(
            {
                "chunk_index": idx,
                "text": normalize_file_text(getattr(chunk, "text", contextual_text)),
                "contextual_text": normalize_file_text(contextual_text),
                "token_count": tokenize(contextual_text, get_embedding_model()),
                "page_number": chunk_page_number(meta),
                "section_title": chunk_section_title(meta),
                "metadata": meta,
            }
        )
    return chunk_rows


def split_oversized_chunk(
    text: str,
    max_tokens: int,
    model_name: str,
) -> list[str]:
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    if not paragraphs:
        return [text]

    out: list[str] = []
    current: list[str] = []
    for paragraph in paragraphs:
        candidate = "\n\n".join(current + [paragraph]) if current else paragraph
        if tokenize(candidate, model_name) <= max_tokens:
            current.append(paragraph)
            continue
        if current:
            out.append("\n\n".join(current))
            current = [paragraph]
        else:
            out.append(paragraph)
            current = []
    if current:
        out.append("\n\n".join(current))
    return out


def enforce_token_limit(
    rows: list[dict[str, Any]],
    max_tokens: int,
    model_name: str,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        text = row["contextual_text"]
        if tokenize(text, model_name) <= max_tokens:
            output.append(row)
            continue
        for part_index, part in enumerate(split_oversized_chunk(text, max_tokens, model_name)):
            output.append(
                {
                    **row,
                    "chunk_index": len(output),
                    "text": part,
                    "contextual_text": part,
                    "token_count": tokenize(part, model_name),
                    "metadata": {
                        **row["metadata"],
                        "split_from_chunk_index": row["chunk_index"],
                        "split_part_index": part_index,
                    },
                }
            )
    return output


def embed_texts(
    model: SentenceTransformer,
    texts: list[str],
) -> list[list[float]]:
    embeddings = model.encode(
        texts,
        batch_size=min(len(texts), CHUNK_BATCH_SIZE_DEFAULT),
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return embeddings.tolist()


def upsert_document_chunk(
    connection: psycopg.Connection[Any],
    *,
    document_id: uuid.UUID,
    chunk_index: int,
    text: str,
    embedding: list[float],
    token_count: int,
    page_number: int | None,
    section_title: str | None,
    metadata: dict[str, Any],
) -> None:
    search_text = text
    with connection.cursor() as cursor:
        cursor.execute(
            """
            insert into document_chunks (
                id,
                document_id,
                chunk_index,
                text,
                embedding,
                search_vector,
                token_count,
                page_number,
                section_title,
                metadata,
                created_at
            )
            values (
                %(id)s,
                %(document_id)s,
                %(chunk_index)s,
                %(text)s,
                %(embedding)s,
                to_tsvector('english', %(search_text)s),
                %(token_count)s,
                %(page_number)s,
                %(section_title)s,
                %(metadata)s,
                now()
            )
            on conflict (document_id, chunk_index) do update set
                text = excluded.text,
                embedding = excluded.embedding,
                search_vector = excluded.search_vector,
                token_count = excluded.token_count,
                page_number = excluded.page_number,
                section_title = excluded.section_title,
                metadata = excluded.metadata
            """,
            {
                "id": uuid.uuid4(),
                "document_id": document_id,
                "chunk_index": chunk_index,
                "text": text,
                "embedding": embedding,
                "search_text": search_text,
                "token_count": token_count,
                "page_number": page_number,
                "section_title": section_title,
                "metadata": Jsonb(metadata),
            },
        )


def collect_markdown_files(limit_files: int | None = None) -> list[Path]:
    files = iter_markdown_files(MARKDOWN_DIR)
    if limit_files is not None:
        return files[:limit_files]
    return files


def run_pipeline(
    smoke: bool = False,
    limit_files: int | None = None,
    chunk_max_tokens: int = 800,
    embedding_batch_size: int = CHUNK_BATCH_SIZE_DEFAULT,
    log_path: Path = DEFAULT_LOG_FILE,
) -> dict[str, Any]:
    configure_logging(log_path)
    logger.info(
        "starting ingestion mode=%s limit_files=%s batch_size=%s",
        "smoke" if smoke else "full",
        limit_files,
        embedding_batch_size,
    )
    ensure_markdown_dir()
    database_url = get_database_url()
    model_name = get_embedding_model()
    dimensions = get_embedding_dimensions()
    token_limit = min(EMBEDDING_TOKEN_LIMIT_DEFAULT, chunk_max_tokens)

    if smoke:
        limit_files = min(limit_files or SMOKE_FILE_COUNT_DEFAULT, SMOKE_FILE_COUNT_DEFAULT)

    manifest_lookup = load_download_manifest()
    converter = DocumentConverter()
    embedding_model = SentenceTransformer(model_name)
    actual_dimensions = embedding_model.get_embedding_dimension()
    if actual_dimensions != dimensions:
            raise RuntimeError(
                f"LOCAL_EMBEDDING_DIMENSIONS={dimensions} does not match {model_name} output dimension {actual_dimensions}"
            )
    logger.info("loaded local embedding model=%s dimensions=%s", model_name, dimensions)
    chunker = build_chunker(model_name, token_limit)
    records: list[ChunkRecord] = []

    with psycopg.connect(database_url) as connection:
        register_vector(connection)
        markdown_files = collect_markdown_files(limit_files)
        chunk_batches: list[dict[str, Any]] = []

        for file_number, markdown_path in enumerate(markdown_files, start=1):
            if markdown_path.name in {DOWNLOADS_MANIFEST.name, OUTPUT_MANIFEST.name}:
                continue

            relative_path = markdown_path.relative_to(MARKDOWN_DIR)
            if len(relative_path.parts) < 2:
                continue

            markdown_text = markdown_path.read_text(encoding="utf-8")
            source_name = markdown_path.name
            logger.info("processing file=%s/%s path=%s", file_number, len(markdown_files), relative_path)
            document_id = ensure_source_rows(connection, manifest_lookup, markdown_path, markdown_text)

            chunk_rows = chunk_document(converter, chunker, markdown_text, source_name)
            chunk_rows = enforce_token_limit(chunk_rows, token_limit, model_name)

            if smoke:
                chunk_rows = chunk_rows[:SMOKE_CHUNK_COUNT_DEFAULT]

            for chunk_row in chunk_rows:
                chunk_batches.append(
                    {
                        "document_id": document_id,
                        "chunk_index": chunk_row["chunk_index"],
                        "text": chunk_row["text"],
                        "contextual_text": chunk_row["contextual_text"],
                        "token_count": chunk_row["token_count"],
                        "page_number": chunk_row["page_number"],
                        "section_title": chunk_row["section_title"],
                        "metadata": {
                            "source_markdown_path": str(relative_path),
                            "year": relative_path.parts[0],
                            "chunk_index": chunk_row["chunk_index"],
                            "page_number": chunk_row["page_number"],
                            "section_title": chunk_row["section_title"],
                            "docling_meta": chunk_row["metadata"],
                        },
                        "ticker": parse_filename(markdown_path)["ticker"],
                        "accession_number": parse_filename(markdown_path)["accession_number"],
                        "year": relative_path.parts[0],
                        "markdown_path": str(relative_path),
                    }
                )

                if len(chunk_batches) >= embedding_batch_size:
                    embed_and_write_batch(
                        connection,
                        embedding_model,
                        chunk_batches,
                        records,
                    )
                    logger.info("embedded and wrote batch size=%s", len(chunk_batches))
                    chunk_batches = []

        if chunk_batches:
            logger.info("embedding final batch size=%s", len(chunk_batches))
            embed_and_write_batch(
                connection,
                embedding_model,
                chunk_batches,
                records,
            )

    manifest = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "mode": "smoke" if smoke else "full",
        "input_dir": str(MARKDOWN_DIR),
        "embedding_model": model_name,
        "embedding_dimensions": dimensions,
        "chunk_max_tokens": token_limit,
        "documents_processed": len({record.accession_number for record in records}),
        "chunks_indexed": len(records),
        "files": [asdict(record) for record in records],
    }
    OUTPUT_MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    logger.info(
        "completed documents=%s chunks=%s manifest=%s",
        manifest["documents_processed"],
        manifest["chunks_indexed"],
        OUTPUT_MANIFEST,
    )
    return manifest


def embed_and_write_batch(
    connection: psycopg.Connection[Any],
    model: SentenceTransformer,
    batch: list[dict[str, Any]],
    records: list[ChunkRecord],
) -> None:
    embeddings = embed_texts(
        model,
        [item["contextual_text"] for item in batch],
    )
    for item, embedding in zip(batch, embeddings, strict=True):
        upsert_document_chunk(
            connection,
            document_id=item["document_id"],
            chunk_index=item["chunk_index"],
            text=item["text"],
            embedding=embedding,
            token_count=item["token_count"],
            page_number=item["page_number"],
            section_title=item["section_title"],
            metadata=item["metadata"],
        )
        records.append(
            ChunkRecord(
                year=item["year"],
                ticker=item["ticker"],
                accession_number=item["accession_number"],
                markdown_path=item["markdown_path"],
                chunk_index=item["chunk_index"],
                token_count=item["token_count"],
                status="ok",
            )
        )
        print(f"[ok] {item['markdown_path']} :: chunk {item['chunk_index']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build document chunks + embeddings in Supabase.")
    parser.add_argument("--smoke", action="store_true", help="Process only one filing and one chunk.")
    parser.add_argument("--limit-files", type=int, default=None, help="Limit how many markdown files to process.")
    parser.add_argument("--chunk-max-tokens", type=int, default=800, help="Token limit for Docling chunking.")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=CHUNK_BATCH_SIZE_DEFAULT,
        help="Number of chunks to embed in each local batch.",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=DEFAULT_LOG_FILE,
        help="Write ingestion progress to this file as well as the terminal.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    result = run_pipeline(
        smoke=args.smoke,
        limit_files=args.limit_files,
        chunk_max_tokens=args.chunk_max_tokens,
        embedding_batch_size=args.batch_size,
        log_path=args.log_file,
    )
    logger.info("indexed %s chunk(s) from %s document(s)", result["chunks_indexed"], result["documents_processed"])
