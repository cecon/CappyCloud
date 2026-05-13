"""merge_multiagent_and_reconcile_branches

Revision ID: 571e75feb2bf
Revises: 6d6cedaba01b, 20260428_000001
Create Date: 2026-04-28 15:19:32.923628

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "571e75feb2bf"
down_revision: Union[str, Sequence[str], None] = ("6d6cedaba01b", "20260428_000001")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
