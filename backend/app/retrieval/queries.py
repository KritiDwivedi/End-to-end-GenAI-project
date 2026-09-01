from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg
from pgvector.psycopg import register_vector

from app.config import settings


@dataclass(slots=True)
class ChunkHit:
    chunk_id: str
    document_id: str
    accession_number: str
    ticker: str
    filing_type: str
    filing_date: str | None
    chunk_index: int
    text: str
    section_title: str | None
    page_number: int | None
    score: float


def _connect() -> psycopg.Connection[Any]:
    return psycopg.connect(settings.database_url_value)


def _base_select() -> str:
    return """
        select
            dc.id as chunk_id,
            dc.document_id,
            sd.accession_number,
            sd.ticker,
            sd.filing_type,
            sd.filing_date::text as filing_date,
            dc.chunk_index,
            dc.text,
            dc.section_title,
            dc.page_number
        from document_chunks dc
        join source_documents sd on sd.id = dc.document_id
    """


def search_chunks_dense(query_embedding: list[float], *, top_k: int = 20) -> list[ChunkHit]:
    sql = (
        _base_select()
        + """
        order by dc.embedding <=> %(query_embedding)s
        limit %(top_k)s
        """
    )
    with _connect() as connection:
        register_vector(connection)
        with connection.cursor() as cursor:
            cursor.execute(sql, {"query_embedding": query_embedding, "top_k": top_k})
            rows = cursor.fetchall()
    hits: list[ChunkHit] = []
    for rank, row in enumerate(rows, start=1):
        hits.append(
            ChunkHit(
                chunk_id=str(row[0]),
                document_id=str(row[1]),
                accession_number=row[2],
                ticker=row[3],
                filing_type=row[4],
                filing_date=row[5],
                chunk_index=row[6],
                text=row[7],
                section_title=row[8],
                page_number=row[9],
                score=1.0 / rank,
            )
        )
    return hits


def search_chunks_sparse(query: str, *, top_k: int = 20) -> list[ChunkHit]:
    sql = (
        _base_select()
        + """
        where dc.search_vector @@ websearch_to_tsquery('english', %(query)s)
        order by ts_rank_cd(dc.search_vector, websearch_to_tsquery('english', %(query)s)) desc
        limit %(top_k)s
        """
    )
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, {"query": query, "top_k": top_k})
            rows = cursor.fetchall()
    hits: list[ChunkHit] = []
    for rank, row in enumerate(rows, start=1):
        hits.append(
            ChunkHit(
                chunk_id=str(row[0]),
                document_id=str(row[1]),
                accession_number=row[2],
                ticker=row[3],
                filing_type=row[4],
                filing_date=row[5],
                chunk_index=row[6],
                text=row[7],
                section_title=row[8],
                page_number=row[9],
                score=1.0 / rank,
            )
        )
    return hits
