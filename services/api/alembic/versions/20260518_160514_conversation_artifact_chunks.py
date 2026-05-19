"""conversation_artifact_chunks

Revision ID: a59a632a33c4
Revises: 8be30de4b8ae
Create Date: 2026-05-18 16:05:14.860169
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a59a632a33c4"
down_revision: str | Sequence[str] | None = "8be30de4b8ae"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Adiciona indexação de artefatos anexados a conversas."""
    op.add_column(
        "message_attachments",
        sa.Column(
            "processing_status",
            sa.String(length=32),
            nullable=False,
            server_default="uploaded",
        ),
    )
    op.add_column(
        "message_attachments",
        sa.Column("chunks_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "message_attachments",
        sa.Column("processing_error", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_message_attachments_processing_status",
        "message_attachments",
        ["processing_status"],
    )

    op.create_table(
        "conversation_artifact_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attachment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("line_start", sa.Integer(), nullable=True),
        sa.Column("line_end", sa.Integer(), nullable=True),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["attachment_id"],
            ["message_attachments.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversation_artifact_chunks_attachment_id",
        "conversation_artifact_chunks",
        ["attachment_id"],
    )
    op.create_index(
        "ix_conversation_artifact_chunks_conversation_id",
        "conversation_artifact_chunks",
        ["conversation_id"],
    )


def downgrade() -> None:
    """Remove indexação de artefatos anexados a conversas."""
    op.drop_index(
        "ix_conversation_artifact_chunks_conversation_id",
        table_name="conversation_artifact_chunks",
    )
    op.drop_index(
        "ix_conversation_artifact_chunks_attachment_id",
        table_name="conversation_artifact_chunks",
    )
    op.drop_table("conversation_artifact_chunks")

    op.drop_index(
        "ix_message_attachments_processing_status",
        table_name="message_attachments",
    )
    op.drop_column("message_attachments", "processing_error")
    op.drop_column("message_attachments", "chunks_count")
    op.drop_column("message_attachments", "processing_status")
