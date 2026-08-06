"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-08-06 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "source_documents",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("cik", sa.String(length=20), nullable=True),
        sa.Column("filing_type", sa.String(length=20), nullable=False),
        sa.Column("filing_date", sa.Date(), nullable=True),
        sa.Column("fiscal_year", sa.Integer(), nullable=True),
        sa.Column("accession_number", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("metadata", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("accession_number", name="uq_source_documents_accession_number"),
    )
    op.create_index("ix_source_documents_ticker", "source_documents", ["ticker"], unique=False)
    op.create_index("ix_source_documents_cik", "source_documents", ["cik"], unique=False)
    op.create_index("ix_source_documents_filing_type", "source_documents", ["filing_type"], unique=False)
    op.create_index("ix_source_documents_ticker_filing_date", "source_documents", ["ticker", "filing_date"], unique=False)
    op.create_index("ix_source_documents_metadata", "source_documents", ["metadata"], unique=False, postgresql_using="gin")

    op.create_table(
        "chat_threads",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=200), server_default=sa.text("'New chat'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_chat_threads_user_id", "chat_threads", ["user_id"], unique=False)
    op.create_index("ix_chat_threads_user_id_updated_at", "chat_threads", ["user_id", "updated_at"], unique=False)

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("document_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("search_vector", sa.dialects.postgresql.TSVECTOR(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section_title", sa.Text(), nullable=True),
        sa.Column("metadata", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_document_id_chunk_index"),
        sa.CheckConstraint("chunk_index >= 0", name="ck_document_chunks_chunk_index_nonnegative"),
        sa.CheckConstraint("token_count IS NULL OR token_count >= 0", name="ck_document_chunks_token_count_nonnegative"),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"], unique=False)
    op.create_index("ix_document_chunks_document_id_chunk_index", "document_chunks", ["document_id", "chunk_index"], unique=False)
    op.create_index("ix_document_chunks_metadata", "document_chunks", ["metadata"], unique=False, postgresql_using="gin")
    op.create_index("ix_document_chunks_search_vector", "document_chunks", ["search_vector"], unique=False, postgresql_using="gin")

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("thread_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.Enum("user", "assistant", "system", name="message_role"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("message_json", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_chat_messages_thread_id", "chat_messages", ["thread_id"], unique=False)
    op.create_index("ix_chat_messages_thread_id_created_at", "chat_messages", ["thread_id", "created_at"], unique=False)
    op.create_index("ix_chat_messages_metadata", "chat_messages", ["metadata"], unique=False, postgresql_using="gin")

    op.create_table(
        "message_citations",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("message_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("document_chunks.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("citation_index", sa.Integer(), nullable=False),
        sa.Column("cited_text", sa.Text(), nullable=True),
        sa.Column("metadata", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("message_id", "citation_index", name="uq_message_citations_message_id_citation_index"),
        sa.CheckConstraint("citation_index >= 0", name="ck_message_citations_citation_index_nonnegative"),
    )
    op.create_index("ix_message_citations_message_id", "message_citations", ["message_id"], unique=False)
    op.create_index("ix_message_citations_chunk_id", "message_citations", ["chunk_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_message_citations_chunk_id", table_name="message_citations")
    op.drop_index("ix_message_citations_message_id", table_name="message_citations")
    op.drop_table("message_citations")

    op.drop_index("ix_chat_messages_metadata", table_name="chat_messages")
    op.drop_index("ix_chat_messages_thread_id_created_at", table_name="chat_messages")
    op.drop_index("ix_chat_messages_thread_id", table_name="chat_messages")
    op.drop_table("chat_messages")

    op.drop_index("ix_document_chunks_search_vector", table_name="document_chunks")
    op.drop_index("ix_document_chunks_metadata", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_id_chunk_index", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")

    op.drop_index("ix_chat_threads_user_id_updated_at", table_name="chat_threads")
    op.drop_index("ix_chat_threads_user_id", table_name="chat_threads")
    op.drop_table("chat_threads")

    op.drop_index("ix_source_documents_metadata", table_name="source_documents")
    op.drop_index("ix_source_documents_ticker_filing_date", table_name="source_documents")
    op.drop_index("ix_source_documents_filing_type", table_name="source_documents")
    op.drop_index("ix_source_documents_cik", table_name="source_documents")
    op.drop_index("ix_source_documents_ticker", table_name="source_documents")
    op.drop_table("source_documents")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
