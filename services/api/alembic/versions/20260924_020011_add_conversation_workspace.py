"""add conversation workspace

Revision ID: 0161751de91d
Revises: c3d461c1cca3
Create Date: 2026-09-24 02:00:11

Gerada com --autogenerate e revisada: além de ``conversations.workspace_id``,
o diff trazia remoções de colunas/índices legados (``agent_id``) e ajustes de
server_default fora do escopo; ficou só a coluna nova, com índice e FK.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0161751de91d"
down_revision: str | Sequence[str] | None = "c3d461c1cca3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("conversations", sa.Column("workspace_id", sa.UUID(), nullable=True))
    op.create_index(
        op.f("ix_conversations_workspace_id"), "conversations", ["workspace_id"], unique=False
    )
    op.create_foreign_key(
        "fk_conversations_workspace_id",
        "conversations",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_conversations_workspace_id", "conversations", type_="foreignkey")
    op.drop_index(op.f("ix_conversations_workspace_id"), table_name="conversations")
    op.drop_column("conversations", "workspace_id")
