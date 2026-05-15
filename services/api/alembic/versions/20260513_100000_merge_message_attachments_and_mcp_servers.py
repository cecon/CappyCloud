"""merge_message_attachments_and_mcp_servers

Revision ID: 20260513_100000
Revises: 20260508_120000, 20260512_223815, 571e75feb2bf
Create Date: 2026-05-13 10:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "20260513_100000"
down_revision: tuple[str, str, str] = ("20260508_120000", "20260512_223815", "571e75feb2bf")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Merge de branches: message_attachments + mcp_servers."""


def downgrade() -> None:
    """No-op."""
