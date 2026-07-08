"""add conversation permission mode

Revision ID: f278fe418b7c
Revises: 20260617_120000
Create Date: 2026-06-17 14:02:16.030535

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f278fe418b7c"
down_revision: Union[str, Sequence[str], None] = "20260617_120000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "conversations",
        sa.Column(
            "permission_mode",
            sa.String(length=32),
            nullable=False,
            server_default="request_permissions",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("conversations", "permission_mode")
