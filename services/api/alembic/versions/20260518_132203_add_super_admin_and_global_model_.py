"""add_super_admin_and_global_model_activation

Revision ID: aedb56ce8bf4
Revises: a3fad75f8225
Create Date: 2026-05-18 13:22:03.892841

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "aedb56ce8bf4"
down_revision: str | Sequence[str] | None = "a3fad75f8225"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SUPER_ADMIN_EMAIL = "eduardocecon@gmail.com"


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column(
            "is_super_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index("ix_users_is_super_admin", "users", ["is_super_admin"])
    op.execute(
        sa.text("UPDATE users SET is_super_admin = true WHERE lower(email) = :email").bindparams(
            email=SUPER_ADMIN_EMAIL
        )
    )
    op.execute(sa.text("UPDATE ai_models SET active = false WHERE tier <> 'free'"))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_users_is_super_admin", table_name="users")
    op.drop_column("users", "is_super_admin")
