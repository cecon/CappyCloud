"""add cache token breakdown

Parcelas de cache por resposta em ``messages`` e ``agent_tasks``:
``cache_read_tokens`` (leitura) e ``cache_write_tokens`` (gravação), ambas já
contidas em ``prompt_tokens``. NULL quando o runtime não informou (linhas
antigas e o runtime openclaude via gRPC).

Revision ID: 32c0550d0576
Revises: 54191f35ea27
Create Date: 2026-10-11 03:11:45.882965

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "32c0550d0576"
down_revision: str | Sequence[str] | None = "54191f35ea27"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("messages", "agent_tasks")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("cache_read_tokens", sa.Integer(), nullable=True))
        op.add_column(table, sa.Column("cache_write_tokens", sa.Integer(), nullable=True))


def downgrade() -> None:
    for table in _TABLES:
        op.drop_column(table, "cache_write_tokens")
        op.drop_column(table, "cache_read_tokens")
