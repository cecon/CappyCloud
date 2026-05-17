"""add_user_role

Adiciona coluna ``role`` à tabela ``users`` com valor padrão ``"user"`` e índice.
Cumpre ADR-005 (Papéis ADMIN/USER e permissões binárias).

Revision ID: 3ae071e0df36
Revises: 9b2e1a4c7f81
Create Date: 2026-05-16 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "3ae071e0df36"
down_revision: str | Sequence[str] | None = "9b2e1a4c7f81"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=16), nullable=False, server_default="user"),
    )
    op.create_index("ix_users_role", "users", ["role"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_users_role", table_name="users")
    op.drop_column("users", "role")
