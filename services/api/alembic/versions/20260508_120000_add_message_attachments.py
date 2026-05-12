"""add_message_attachments

Tabela para armazenar anexos (inicialmente imagens) carregados pelo utilizador
numa conversa. O ficheiro fica num volume Docker; aqui guardamos apenas o
metadado e a **descrição textual** gerada por um modelo de visão (vision
describer) — essa descrição é injetada no prompt do agente, permitindo que
modelos sem capacidade multimodal raciocinem sobre o conteúdo da imagem.

Revision ID: 20260508_120000
Revises: 8272efee3060
Create Date: 2026-05-08 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811  # alias claro p/ ler nas Column()

revision: str = "20260508_120000"
down_revision: str | Sequence[str] | None = "8272efee3060"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create message_attachments table."""
    op.create_table(
        "message_attachments",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "message_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="image"),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("vision_description", sa.Text(), nullable=True),
        sa.Column("vision_model_used", sa.String(length=256), nullable=True),
        sa.Column("uploaded_by", PgUUID(as_uuid=True), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_message_attachments_conv_uploaded",
        "message_attachments",
        ["conversation_id", "uploaded_at"],
    )


def downgrade() -> None:
    """Drop message_attachments table."""
    op.drop_index("ix_message_attachments_conv_uploaded", table_name="message_attachments")
    op.drop_table("message_attachments")
