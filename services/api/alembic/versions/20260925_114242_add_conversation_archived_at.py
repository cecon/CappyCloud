"""add conversation archived_at

Conversas arquivadas somem da lista do usuário sem serem apagadas.

Revision ID: d6d1ab2448e4
Revises: 7858fdf18f45
Create Date: 2026-09-25 11:42:42.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d6d1ab2448e4"
down_revision: str | Sequence[str] | None = "7858fdf18f45"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversations", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        op.f("ix_conversations_archived_at"), "conversations", ["archived_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_conversations_archived_at"), table_name="conversations")
    op.drop_column("conversations", "archived_at")
