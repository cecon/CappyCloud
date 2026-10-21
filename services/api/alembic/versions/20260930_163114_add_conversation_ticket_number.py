"""add conversation ticket_number

Número do chamado (Zendesk etc.) por conversa, e workspace que o exige.

Revision ID: 8ed57121871e
Revises: 030b226d7d69
Create Date: 2026-09-30 16:31:14.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8ed57121871e"
down_revision: str | Sequence[str] | None = "030b226d7d69"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("ticket_number", sa.String(64), nullable=True))
    op.create_index("ix_conversations_ticket_number", "conversations", ["ticket_number"])
    op.add_column(
        "workspaces",
        sa.Column("require_ticket", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("workspaces", "require_ticket")
    op.drop_index("ix_conversations_ticket_number", table_name="conversations")
    op.drop_column("conversations", "ticket_number")
