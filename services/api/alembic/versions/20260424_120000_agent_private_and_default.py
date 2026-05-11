"""agent_private_and_default

Adiciona ao modelo Agent:
  - owner_id   UUID nullable FK → users(id): quando preenchido, o agente é privado
  - is_default BOOLEAN: apenas um agente pode ter is_default=TRUE (índice parcial único)

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-24 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("owner_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_agents_owner",
        "agents",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_agents_owner_id", "agents", ["owner_id"])

    op.add_column(
        "agents",
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    # Garante que no máximo um agente seja o padrão.
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX ix_agents_is_default_unique "
            "ON agents (is_default) WHERE is_default = TRUE"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_agents_is_default_unique"))
    op.drop_column("agents", "is_default")

    op.drop_index("ix_agents_owner_id", table_name="agents")
    op.drop_constraint("fk_agents_owner", "agents", type_="foreignkey")
    op.drop_column("agents", "owner_id")
