"""add workspace admin flag

``user_workspace_access.is_admin``: o usuário administra aquele workspace
(conversas, relatórios, pessoas e CLAUDE.md dele) sem virar ADMIN global.
Ligado e desligado só pelo super admin.

Revision ID: 7d3a91c4e2b8
Revises: 32c0550d0576
Create Date: 2026-10-21 16:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7d3a91c4e2b8"
down_revision: str | Sequence[str] | None = "32c0550d0576"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_workspace_access",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("user_workspace_access", "is_admin")
