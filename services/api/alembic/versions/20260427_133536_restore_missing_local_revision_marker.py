"""restore missing local revision marker

Revision ID: a150801ba0db
Revises: 09b31aab7f64
Create Date: 2026-04-27 13:35:36.303846

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "a150801ba0db"
down_revision: Union[str, Sequence[str], None] = "09b31aab7f64"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
