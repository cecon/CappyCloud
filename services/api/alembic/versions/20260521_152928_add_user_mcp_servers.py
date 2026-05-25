"""add_user_mcp_servers

Revision ID: e89304b857a9
Revises: 71898a1bb00d
Create Date: 2026-05-21 15:29:28.285756

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "e89304b857a9"
down_revision: str | Sequence[str] | None = "71898a1bb00d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "user_mcp_servers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_preview", sa.String(length=16), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "name", name="uq_user_mcp_name"),
        sa.UniqueConstraint("token_hash", name="uq_user_mcp_token_hash"),
    )
    op.create_index("ix_user_mcp_servers_user_id", "user_mcp_servers", ["user_id"])
    op.create_index(
        "ix_user_mcp_servers_repository_id",
        "user_mcp_servers",
        ["repository_id"],
    )
    op.create_index("ix_user_mcp_servers_enabled", "user_mcp_servers", ["enabled"])
    op.create_index("ix_user_mcp_servers_token_hash", "user_mcp_servers", ["token_hash"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_user_mcp_servers_token_hash", table_name="user_mcp_servers")
    op.drop_index("ix_user_mcp_servers_enabled", table_name="user_mcp_servers")
    op.drop_index("ix_user_mcp_servers_repository_id", table_name="user_mcp_servers")
    op.drop_index("ix_user_mcp_servers_user_id", table_name="user_mcp_servers")
    op.drop_table("user_mcp_servers")
