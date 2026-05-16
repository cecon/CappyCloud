"""add_repository_confluence_url

Revision ID: 7ae83e67c053
Revises: 20260513_130000
Create Date: 2026-05-16 00:27:51.180620

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7ae83e67c053"
down_revision: str | Sequence[str] | None = "20260513_130000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "repositories",
        sa.Column("confluence_url", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("repositories", "confluence_url")
