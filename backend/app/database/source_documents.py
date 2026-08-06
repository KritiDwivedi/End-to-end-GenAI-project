from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Date, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, utc_now

if TYPE_CHECKING:
    from app.database.document_chunks import DocumentChunk


class SourceDocument(Base):
    __tablename__ = "source_documents"
    __table_args__ = (
        UniqueConstraint("accession_number", name="uq_source_documents_accession_number"),
        Index("ix_source_documents_ticker_filing_date", "ticker", "filing_date"),
        Index("ix_source_documents_metadata", "metadata", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    cik: Mapped[str | None] = mapped_column(String(20), index=True)
    filing_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    filing_date: Mapped[date | None] = mapped_column(Date)
    fiscal_year: Mapped[int | None] = mapped_column(Integer)
    accession_number: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    chunks: Mapped[list[DocumentChunk]] = relationship(back_populates="document", cascade="all, delete-orphan")
