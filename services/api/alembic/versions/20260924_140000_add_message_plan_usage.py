"""add message plan usage

Revision ID: ff3bc9b4993d
Revises: badd8f7956d2
Create Date: 2026-09-24 12:53:18

Gerada com --autogenerate e revisada: o diff trazia remoções de tabelas e
índices legados fora do escopo; ficou só ``messages.plan_usage`` (uso das
janelas de 5h/7d da assinatura do Claude CLI ao fim de cada resposta).
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "ff3bc9b4993d"
down_revision: str | Sequence[str] | None = "badd8f7956d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("messages", sa.Column("plan_usage", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("messages", "plan_usage")
