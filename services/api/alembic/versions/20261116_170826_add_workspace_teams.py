"""add workspace teams

Times do workspace para o relatório de uso: ``workspace_teams`` (nome único por
workspace, sem diferenciar maiúsculas) e ``user_workspace_access.team_id``, o
time da pessoa naquele workspace. Apagar o time deixa a pessoa sem time.

Revision ID: 8f901beadab1
Revises: 7d3a91c4e2b8
Create Date: 2026-11-16 17:08:26.117618

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "8f901beadab1"
down_revision: str | Sequence[str] | None = "7d3a91c4e2b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspace_teams",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_workspace_teams_workspace_id", "workspace_teams", ["workspace_id"])
    op.create_index(
        "uq_workspace_teams_name",
        "workspace_teams",
        ["workspace_id", sa.text("lower(name)")],
        unique=True,
    )
    op.add_column(
        "user_workspace_access",
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "workspace_teams.id",
                ondelete="SET NULL",
                name="fk_user_workspace_access_team_id",
            ),
            nullable=True,
        ),
    )
    op.create_index("ix_user_workspace_access_team_id", "user_workspace_access", ["team_id"])


def downgrade() -> None:
    op.drop_index("ix_user_workspace_access_team_id", table_name="user_workspace_access")
    op.drop_constraint(
        "fk_user_workspace_access_team_id", "user_workspace_access", type_="foreignkey"
    )
    op.drop_column("user_workspace_access", "team_id")
    op.drop_index("uq_workspace_teams_name", table_name="workspace_teams")
    op.drop_index("ix_workspace_teams_workspace_id", table_name="workspace_teams")
    op.drop_table("workspace_teams")
