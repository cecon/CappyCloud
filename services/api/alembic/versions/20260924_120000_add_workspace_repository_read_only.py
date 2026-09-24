"""add workspace repository read_only

Revision ID: 5b7e2a91d4c3
Revises: 0161751de91d
Create Date: 2026-09-24 12:00:00

Repositório somente leitura no workspace: o agente consulta o clone do
workspace, sem worktree nem branch de sessão, e ele fica fora do diff e do PR.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "5b7e2a91d4c3"
down_revision: str | Sequence[str] | None = "0161751de91d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "workspace_repositories",
        sa.Column("read_only", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("workspace_repositories", "read_only")
