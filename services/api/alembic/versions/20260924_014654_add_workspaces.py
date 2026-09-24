"""add workspaces

Revision ID: c3d461c1cca3
Revises: 6c4f9b2a7d81
Create Date: 2026-09-24 01:46:54.027616

Gerada com --autogenerate e revisada: o diff contra o banco trazia DROPs de
tabelas legadas não mapeadas no ORM (cappy_sessions, project_suggestions,
tabelas antigas de chat); ficaram só as três tabelas de workspace.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c3d461c1cca3"
down_revision: str | Sequence[str] | None = "6c4f9b2a7d81"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "workspaces",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("sandbox_id", sa.UUID(), nullable=False),
        sa.Column("claude_md", sa.Text(), server_default="", nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("sync_status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("sync_error", sa.Text(), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["sandbox_id"], ["sandboxes.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workspaces_sandbox_id"), "workspaces", ["sandbox_id"], unique=False)
    op.create_index(op.f("ix_workspaces_slug"), "workspaces", ["slug"], unique=True)

    op.create_table(
        "user_workspace_access",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "workspace_id", name="uq_user_workspace_access"),
    )
    op.create_index(
        op.f("ix_user_workspace_access_user_id"), "user_workspace_access", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_user_workspace_access_workspace_id"),
        "user_workspace_access",
        ["workspace_id"],
        unique=False,
    )

    op.create_table(
        "workspace_repositories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("repository_id", sa.UUID(), nullable=False),
        sa.Column("alias", sa.String(length=128), nullable=False),
        sa.Column("base_branch", sa.String(length=256), server_default="", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "alias", name="uq_workspace_repository_alias"),
        sa.UniqueConstraint("workspace_id", "repository_id", name="uq_workspace_repository"),
    )
    op.create_index(
        op.f("ix_workspace_repositories_repository_id"),
        "workspace_repositories",
        ["repository_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workspace_repositories_workspace_id"),
        "workspace_repositories",
        ["workspace_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_workspace_repositories_workspace_id"), table_name="workspace_repositories"
    )
    op.drop_index(
        op.f("ix_workspace_repositories_repository_id"), table_name="workspace_repositories"
    )
    op.drop_table("workspace_repositories")
    op.drop_index(op.f("ix_user_workspace_access_workspace_id"), table_name="user_workspace_access")
    op.drop_index(op.f("ix_user_workspace_access_user_id"), table_name="user_workspace_access")
    op.drop_table("user_workspace_access")
    op.drop_index(op.f("ix_workspaces_slug"), table_name="workspaces")
    op.drop_index(op.f("ix_workspaces_sandbox_id"), table_name="workspaces")
    op.drop_table("workspaces")
