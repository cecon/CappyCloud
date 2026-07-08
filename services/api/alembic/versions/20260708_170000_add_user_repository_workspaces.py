"""add_user_repository_workspaces

Revision ID: 20260708_170000
Revises: 8ec592ec36ff
Create Date: 2026-07-08 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260708_170000"
down_revision: Union[str, Sequence[str], None] = "8ec592ec36ff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "user_repository_workspaces",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("repository_id", sa.UUID(), nullable=False),
        sa.Column("sandbox_id", sa.UUID(), nullable=True),
        sa.Column("sandbox_key", sa.String(length=128), server_default="default", nullable=False),
        sa.Column("base_branch", sa.String(length=256), nullable=False),
        sa.Column("workspace_path", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="preparing", nullable=False),
        sa.Column("health_message", sa.Text(), server_default="", nullable=False),
        sa.Column("last_prepared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sandbox_id"], ["sandboxes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "repository_id",
            "sandbox_key",
            "base_branch",
            name="uq_user_repo_workspace_scope",
        ),
        sa.UniqueConstraint("workspace_path"),
    )
    op.create_index(
        op.f("ix_user_repository_workspaces_repository_id"),
        "user_repository_workspaces",
        ["repository_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_repository_workspaces_sandbox_id"),
        "user_repository_workspaces",
        ["sandbox_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_repository_workspaces_sandbox_key"),
        "user_repository_workspaces",
        ["sandbox_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_repository_workspaces_status"),
        "user_repository_workspaces",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_repository_workspaces_user_id"),
        "user_repository_workspaces",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_user_repository_workspaces_user_id"), table_name="user_repository_workspaces")
    op.drop_index(op.f("ix_user_repository_workspaces_status"), table_name="user_repository_workspaces")
    op.drop_index(op.f("ix_user_repository_workspaces_sandbox_key"), table_name="user_repository_workspaces")
    op.drop_index(op.f("ix_user_repository_workspaces_sandbox_id"), table_name="user_repository_workspaces")
    op.drop_index(
        op.f("ix_user_repository_workspaces_repository_id"),
        table_name="user_repository_workspaces",
    )
    op.drop_table("user_repository_workspaces")
