from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, utc_now

if TYPE_CHECKING:
    from app.database.chat_messages import ChatMessage
    from app.database.document_chunks import DocumentChunk


class MessageCitation(Base):
    __tablename__ = "message_citations"
    __table_args__ = (
        CheckConstraint("citation_index >= 0", name="ck_message_citations_citation_index_nonnegative"),
        UniqueConstraint("message_id", "citation_index", name="uq_message_citations_message_id_citation_index"),
        Index("ix_message_citations_message_id", "message_id"),
        Index("ix_message_citations_chunk_id", "chunk_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False)
    chunk_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("document_chunks.id", ondelete="RESTRICT"), nullable=False)
    citation_index: Mapped[int] = mapped_column(Integer, nullable=False)
    cited_text: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    message: Mapped[ChatMessage] = relationship(back_populates="citations")
    chunk: Mapped[DocumentChunk] = relationship(back_populates="citations")
