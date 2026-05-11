"""legacy_agent_prompt_noop

Revision ID: 09b31aab7f64
Revises: 20260424_170558
Create Date: 2026-04-25 12:03:23.448825
"""

from __future__ import annotations

from typing import Sequence, Union

revision: str = "09b31aab7f64"
down_revision: Union[str, Sequence[str], None] = "20260424_170558"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Legacy placeholder kept to preserve the Alembic revision chain."""


def downgrade() -> None:
    """No-op downgrade for the legacy placeholder."""
