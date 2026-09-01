# /// script
# requires-python = ">=3.12"
# dependencies = ["sqlalchemy", "psycopg[binary]"]
# ///
from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
BACKEND_DIR = PROJECT_DIR / "backend"
BACKEND_ENV_FILE = BACKEND_DIR / ".env"
MARKDOWN_DIR = BASE_DIR / "markdown"
DOWNLOADS_MANIFEST = BASE_DIR / "downloads" / "manifest.json"
OUTPUT_MANIFEST = MARKDOWN_DIR / "import_manifest.json"
CLEAR_EXISTING_ROWS = False


@dataclass(slots=True)
class ImportRecord:
    year: str
    ticker: str
    filing_date: str
    accession_number: str
    markdown_path: str
    status: str


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_filename(path: Path) -> dict[str, str]:
    stem = path.stem
    ticker, form, filing_date, accession_number = stem.split("_", 3)
    return {
        "ticker": ticker.upper(),
        "form": form.upper(),
        "filing_date": filing_date,
        "accession_number": accession_number,
    }


def build_download_lookup() -> dict[str, dict[str, str]]:
    if not DOWNLOADS_MANIFEST.exists():
        return {}

    manifest = load_json(DOWNLOADS_MANIFEST)
    lookup: dict[str, dict[str, str]] = {}
    for item in manifest.get("filings", []):
        lookup[item["local_path"]] = item
    return lookup


def infer_company_name(ticker: str) -> str:
    return {
        "AAPL": "Apple",
        "AMZN": "Amazon",
        "GOOGL": "Alphabet",
        "MSFT": "Microsoft",
        "NVDA": "NVIDIA",
    }.get(ticker.upper(), ticker.upper())


def iter_markdown_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.md") if path.is_file())


def ensure_database_url() -> str:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        if BACKEND_ENV_FILE.exists():
            for line in BACKEND_ENV_FILE.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                key, value = stripped.split("=", 1)
                if key.strip() == "DATABASE_URL":
                    database_url = value.strip().strip('"').strip("'")
                    break

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is required. Set it in the environment or backend/.env"
        )
    return database_url


def load_markdown_documents() -> dict[str, Any]:
    if not MARKDOWN_DIR.exists():
        raise FileNotFoundError(f"Markdown directory not found: {MARKDOWN_DIR}")

    download_lookup = build_download_lookup()
    database_url = make_url(ensure_database_url()).set(drivername="postgresql+psycopg")
    engine = create_engine(database_url.render_as_string(hide_password=False), future=True)
    records: list[ImportRecord] = []

    with engine.begin() as connection:
        if CLEAR_EXISTING_ROWS:
            connection.execute(text("delete from source_documents"))

        for markdown_path in iter_markdown_files(MARKDOWN_DIR):
            if markdown_path.name == OUTPUT_MANIFEST.name:
                continue

            relative_path = markdown_path.relative_to(MARKDOWN_DIR)
            if len(relative_path.parts) < 2:
                continue

            file_info = parse_filename(markdown_path)
            year = relative_path.parts[0]
            source_item = download_lookup.get(str(relative_path.with_suffix(".htm"))) or download_lookup.get(
                str(relative_path.with_suffix(".html"))
            )
            content_markdown = markdown_path.read_text(encoding="utf-8")
            metadata = {
                "year": year,
                "ticker": file_info["ticker"],
                "form": file_info["form"],
                "filing_date": file_info["filing_date"],
                "accession_number": file_info["accession_number"],
                "source_manifest_path": source_item["local_path"] if source_item else None,
                "source_url": source_item["source_url"] if source_item else None,
            }

            connection.execute(
                text(
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
                        :id,
                        :company_name,
                        :ticker,
                        :cik,
                        :filing_type,
                        :filing_date,
                        :fiscal_year,
                        :accession_number,
                        :source_url,
                        :content_markdown,
                        :metadata,
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
                    """
                ),
                {
                    "id": uuid.uuid4(),
                    "company_name": infer_company_name(file_info["ticker"]),
                    "ticker": file_info["ticker"],
                    "cik": source_item["cik"] if source_item else None,
                    "filing_type": file_info["form"],
                    "filing_date": date.fromisoformat(file_info["filing_date"]),
                    "fiscal_year": int(file_info["filing_date"][:4]),
                    "accession_number": file_info["accession_number"],
                    "source_url": source_item["source_url"] if source_item else None,
                    "content_markdown": content_markdown,
                    "metadata": json.dumps(metadata),
                },
            )

            records.append(
                ImportRecord(
                    year=year,
                    ticker=file_info["ticker"],
                    filing_date=file_info["filing_date"],
                    accession_number=file_info["accession_number"],
                    markdown_path=str(relative_path),
                    status="ok",
                )
            )
            print(f"[ok] {relative_path}")

    manifest = {
        "source": str(MARKDOWN_DIR),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "database_url_present": bool(os.environ.get("DATABASE_URL")),
        "imported_count": len(records),
        "files": [asdict(record) for record in records],
    }
    OUTPUT_MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    result = load_markdown_documents()
    print(f"Imported {result['imported_count']} markdown file(s) into source_documents.")
    print(f"Manifest: {OUTPUT_MANIFEST}")
