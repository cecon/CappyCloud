"""add_repository_confluence_space

Revision ID: 9b2e1a4c7f81
Revises: 7ae83e67c053
Create Date: 2026-05-16 04:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9b2e1a4c7f81"
down_revision: str | Sequence[str] | None = "7ae83e67c053"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "repositories",
        sa.Column("confluence_space", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("repositories", "confluence_space")
