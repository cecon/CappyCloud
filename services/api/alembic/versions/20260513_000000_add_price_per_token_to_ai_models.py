"""add_price_per_token_to_ai_models

Revision ID: 50ceffcbc437
Revises: 2e0474891143
Create Date: 2026-05-13 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "50ceffcbc437"
down_revision: str | None = "2e0474891143"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing = {c["name"] for c in inspector.get_columns("ai_models")}
    if "input_price_per_token" not in existing:
        op.add_column("ai_models", sa.Column("input_price_per_token", sa.Float(), nullable=True))
    if "output_price_per_token" not in existing:
        op.add_column("ai_models", sa.Column("output_price_per_token", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_models", "output_price_per_token")
    op.drop_column("ai_models", "input_price_per_token")
