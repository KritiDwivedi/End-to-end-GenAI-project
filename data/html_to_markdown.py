# /// script
# requires-python = ">=3.12"
# dependencies = ["docling"]
# ///
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, asdict
from datetime import UTC, datetime
from pathlib import Path

from docling.document_converter import DocumentConverter


BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "downloads"
OUTPUT_DIR = BASE_DIR / "markdown"
CLEAR_OUTPUT_DIR = True
SUPPORTED_SUFFIXES = {".htm", ".html"}


@dataclass(slots=True)
class ConversionRecord:
    year: str
    source_path: str
    markdown_path: str
    status: str


def iter_html_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )


def convert_html_tree() -> dict[str, object]:
    if not INPUT_DIR.exists():
        raise FileNotFoundError(f"Input directory not found: {INPUT_DIR}")

    if CLEAR_OUTPUT_DIR and OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    converter = DocumentConverter()
    records: list[ConversionRecord] = []
    converted = 0
    failed = 0

    for source_path in iter_html_files(INPUT_DIR):
        relative_source = source_path.relative_to(INPUT_DIR)
        year = relative_source.parts[0] if relative_source.parts else "unknown"
        target_path = OUTPUT_DIR / relative_source.with_suffix(".md")
        target_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            result = converter.convert(source_path)
            markdown = result.document.export_to_markdown()
            target_path.write_text(markdown.rstrip() + "\n", encoding="utf-8")
            records.append(
                ConversionRecord(
                    year=year,
                    source_path=str(relative_source),
                    markdown_path=str(target_path.relative_to(OUTPUT_DIR)),
                    status="ok",
                )
            )
            converted += 1
            print(f"[ok] {relative_source} -> {target_path.relative_to(OUTPUT_DIR)}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            records.append(
                ConversionRecord(
                    year=year,
                    source_path=str(relative_source),
                    markdown_path=str(target_path.relative_to(OUTPUT_DIR)),
                    status=f"error: {exc.__class__.__name__}",
                )
            )
            print(f"[err] {relative_source}: {exc}")

    manifest = {
        "source": "data/downloads",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "input_dir": str(INPUT_DIR),
        "output_dir": str(OUTPUT_DIR),
        "converted_count": converted,
        "failed_count": failed,
        "files": [asdict(record) for record in records],
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


if __name__ == "__main__":
    result = convert_html_tree()
    print(
        f"Converted {result['converted_count']} file(s), "
        f"{result['failed_count']} failed."
    )
    print(f"Manifest: {OUTPUT_DIR / 'manifest.json'}")
