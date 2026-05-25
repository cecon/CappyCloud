"""add_mcp_tool_invocations

Revision ID: ded3d62e1adb
Revises: 5d8dd85798ce
Create Date: 2026-05-25 15:03:22.123097

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "ded3d62e1adb"
down_revision: Union[str, Sequence[str], None] = "5d8dd85798ce"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "mcp_tool_invocations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("trace_id", sa.UUID(), nullable=False),
        sa.Column("server_id", sa.UUID(), nullable=True),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("repo_id", sa.UUID(), nullable=True),
        sa.Column("tool_name", sa.Text(), nullable=False),
        sa.Column(
            "arguments_sanitized",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_summary", sa.String(length=500), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("response_bytes", sa.Integer(), nullable=True),
        sa.Column("response_hash", sa.String(length=64), nullable=True),
        sa.Column("materialized", sa.Boolean(), nullable=True),
        sa.Column("caller_user_agent", sa.Text(), nullable=True),
        sa.Column("caller_session_id", sa.String(length=200), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["repo_id"], ["repositories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["server_id"], ["user_mcp_servers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_mcp_invocations_created_at",
        "mcp_tool_invocations",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "idx_mcp_invocations_tool_created",
        "mcp_tool_invocations",
        ["tool_name", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_mcp_invocations_repo_created",
        "mcp_tool_invocations",
        ["repo_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_mcp_invocations_trace",
        "mcp_tool_invocations",
        ["trace_id"],
        unique=False,
    )
    op.create_index(
        "idx_mcp_invocations_status_created",
        "mcp_tool_invocations",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_mcp_invocations_user_created",
        "mcp_tool_invocations",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_mcp_invocations_user_created", table_name="mcp_tool_invocations")
    op.drop_index("idx_mcp_invocations_status_created", table_name="mcp_tool_invocations")
    op.drop_index("idx_mcp_invocations_trace", table_name="mcp_tool_invocations")
    op.drop_index("idx_mcp_invocations_repo_created", table_name="mcp_tool_invocations")
    op.drop_index("idx_mcp_invocations_tool_created", table_name="mcp_tool_invocations")
    op.drop_index("idx_mcp_invocations_created_at", table_name="mcp_tool_invocations")
    op.drop_table("mcp_tool_invocations")
