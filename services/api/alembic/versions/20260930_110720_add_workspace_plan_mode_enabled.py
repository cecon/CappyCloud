"""add workspace plan_mode_enabled

Modo de planejamento passa a ser ligado por workspace (desligado por padrão).

Revision ID: 030b226d7d69
Revises: 6e74446d790f
Create Date: 2026-09-30 11:07:20.622900

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "030b226d7d69"
down_revision: str | Sequence[str] | None = "6e74446d790f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column("plan_mode_enabled", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("workspaces", "plan_mode_enabled")
