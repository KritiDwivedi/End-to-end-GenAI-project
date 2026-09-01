from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, utc_now

if TYPE_CHECKING:
    from app.database.message_citations import MessageCitation
    from app.database.source_documents import SourceDocument


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_document_id_chunk_index"),
        CheckConstraint("chunk_index >= 0", name="ck_document_chunks_chunk_index_nonnegative"),
        CheckConstraint("token_count IS NULL OR token_count >= 0", name="ck_document_chunks_token_count_nonnegative"),
        Index("ix_document_chunks_document_id_chunk_index", "document_id", "chunk_index"),
        Index("ix_document_chunks_metadata", "metadata", postgresql_using="gin"),
        Index("ix_document_chunks_search_vector", "search_vector", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384))
    search_vector: Mapped[Any | None] = mapped_column(TSVECTOR)
    token_count: Mapped[int | None] = mapped_column(Integer)
    page_number: Mapped[int | None] = mapped_column(Integer)
    section_title: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    document: Mapped[SourceDocument] = relationship(back_populates="chunks")
    citations: Mapped[list[MessageCitation]] = relationship(back_populates="chunk")
