"""legacy_agent_profile_noop

Revision ID: 20260424_170558
Revises: b2c3d4e5f6a7
Create Date: 2026-04-24 17:05:58
"""

from __future__ import annotations

from typing import Sequence, Union

revision: str = "20260424_170558"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Legacy placeholder kept to preserve the Alembic revision chain."""


def downgrade() -> None:
    """No-op downgrade for the legacy placeholder."""
