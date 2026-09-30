"""add user password_reset_expires_at

Validade (24 h) da senha temporária da redefinição pelo admin.

Revision ID: 6e74446d790f
Revises: d6d1ab2448e4
Create Date: 2026-09-29 12:45:44.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6e74446d790f"
down_revision: str | Sequence[str] | None = "d6d1ab2448e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_reset_expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "password_reset_expires_at")
