"""add_mcp_servers_table

Revision ID: a1b2c3d4e5f6
Revises: 50ceffcbc437
Create Date: 2026-05-12 22:38:15.000000

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "50ceffcbc437"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria tabela mcp_servers para configuração de servidores MCP por utilizador."""
    op.create_table(
        "mcp_servers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("command", sa.String(256), nullable=False),
        sa.Column(
            "args",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "env",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_mcp_user_name"),
    )
    op.create_index("ix_mcp_servers_user_id", "mcp_servers", ["user_id"])
    op.create_index("ix_mcp_servers_enabled", "mcp_servers", ["enabled"])


def downgrade() -> None:
    """Remove tabela mcp_servers."""
    op.drop_index("ix_mcp_servers_enabled", table_name="mcp_servers")
    op.drop_index("ix_mcp_servers_user_id", table_name="mcp_servers")
    op.drop_table("mcp_servers")
