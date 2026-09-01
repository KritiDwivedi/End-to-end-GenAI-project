from __future__ import annotations

import uuid
from pydantic import BaseModel, Field


class RetrievalQuery(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=8, ge=1, le=50)
    dense_k: int = Field(default=20, ge=1, le=100)
    sparse_k: int = Field(default=20, ge=1, le=100)


class RetrievedChunk(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    accession_number: str
    ticker: str
    filing_type: str
    filing_date: str | None = None
    chunk_index: int
    text: str
    section_title: str | None = None
    page_number: int | None = None
    dense_rank: int | None = None
    sparse_rank: int | None = None
    fused_rank: int | None = None
    score: float = 0.0


class RetrievalResult(BaseModel):
    query: str
    chunks: list[RetrievedChunk]
