"""default_full_access_permission_mode

Revision ID: 861952b7c568
Revises: b6fbc5d81584
Create Date: 2026-07-21 12:41:23.213456

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '861952b7c568'
down_revision: Union[str, Sequence[str], None] = 'b6fbc5d81584'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "conversations",
        "permission_mode",
        existing_type=sa.String(length=32),
        server_default="bypass_permissions",
        existing_nullable=False,
    )
    op.alter_column(
        "user_preferences",
        "default_permission_mode",
        existing_type=sa.String(length=32),
        server_default="bypass_permissions",
        existing_nullable=False,
    )
    op.execute(
        "UPDATE conversations "
        "SET permission_mode = 'bypass_permissions' "
        "WHERE permission_mode = 'request_permissions'"
    )
    op.execute(
        "UPDATE user_preferences "
        "SET default_permission_mode = 'bypass_permissions' "
        "WHERE default_permission_mode = 'request_permissions'"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "conversations",
        "permission_mode",
        existing_type=sa.String(length=32),
        server_default="request_permissions",
        existing_nullable=False,
    )
    op.alter_column(
        "user_preferences",
        "default_permission_mode",
        existing_type=sa.String(length=32),
        server_default="request_permissions",
        existing_nullable=False,
    )
    op.execute(
        "UPDATE conversations "
        "SET permission_mode = 'request_permissions' "
        "WHERE permission_mode = 'bypass_permissions'"
    )
    op.execute(
        "UPDATE user_preferences "
        "SET default_permission_mode = 'request_permissions' "
        "WHERE default_permission_mode = 'bypass_permissions'"
    )
