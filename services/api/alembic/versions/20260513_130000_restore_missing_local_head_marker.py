"""restore missing local head marker

Revision ID: 20260513_130000
Revises: 20260513_100000
Create Date: 2026-05-13 13:00:00.000000

"""

from typing import Sequence


# revision identifiers, used by Alembic.
revision: str = "20260513_130000"
down_revision: str | Sequence[str] | None = "20260513_100000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Legacy placeholder kept to preserve the Alembic revision chain."""


def downgrade() -> None:
    """No-op downgrade for the placeholder revision."""
