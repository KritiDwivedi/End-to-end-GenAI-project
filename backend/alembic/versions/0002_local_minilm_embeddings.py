"""switch document chunk embeddings to local MiniLM

Revision ID: 0002_local_minilm_embeddings
Revises: 0001_initial_schema
"""

from __future__ import annotations

from alembic import op
from pgvector.sqlalchemy import Vector


revision = "0002_local_minilm_embeddings"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Old 1536-dimensional vectors cannot be used with MiniLM's 384 dimensions.
    op.execute("UPDATE document_chunks SET embedding = NULL")
    op.alter_column(
        "document_chunks",
        "embedding",
        existing_type=Vector(1536),
        type_=Vector(384),
        existing_nullable=True,
        postgresql_using="embedding::vector(384)",
    )


def downgrade() -> None:
    op.execute("UPDATE document_chunks SET embedding = NULL")
    op.alter_column(
        "document_chunks",
        "embedding",
        existing_type=Vector(384),
        type_=Vector(1536),
        existing_nullable=True,
        postgresql_using="embedding::vector(1536)",
    )
