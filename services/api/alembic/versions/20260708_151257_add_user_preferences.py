"""add_user_preferences

Revision ID: 8ec592ec36ff
Revises: 20260622_120000
Create Date: 2026-07-08 15:12:57.023631

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "8ec592ec36ff"
down_revision: Union[str, Sequence[str], None] = "20260622_120000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "default_permission_mode",
            sa.String(length=32),
            server_default="request_permissions",
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("user_preferences")
