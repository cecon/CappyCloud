"""add_repository_confluence_labels

Revision ID: 4b4ad3bb8b73
Revises: a59a632a33c4
Create Date: 2026-05-19 15:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "4b4ad3bb8b73"
down_revision: str | Sequence[str] | None = "a59a632a33c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    """Upgrade schema."""
    if not _has_column("repositories", "confluence_labels"):
        op.add_column(
            "repositories",
            sa.Column(
                "confluence_labels",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default="[]",
            ),
        )


def downgrade() -> None:
    """Downgrade schema."""
    if _has_column("repositories", "confluence_labels"):
        op.drop_column("repositories", "confluence_labels")
