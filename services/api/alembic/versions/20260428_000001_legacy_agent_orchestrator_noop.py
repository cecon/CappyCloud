"""legacy_agent_orchestrator_noop

Revision ID: 20260428_000001
Revises: 09b31aab7f64
Create Date: 2026-04-28 00:00:01
"""

from __future__ import annotations

from typing import Sequence, Union

revision: str = "20260428_000001"
down_revision: Union[str, Sequence[str], None] = "09b31aab7f64"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Legacy placeholder kept to preserve the Alembic revision chain."""


def downgrade() -> None:
    """No-op downgrade for the legacy placeholder."""
