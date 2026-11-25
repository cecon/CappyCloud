"""add workspace prompt template

``workspaces.prompt_template``: texto que já vem na caixa de mensagem de toda
conversa nova do workspace, para a pessoa completar antes de enviar. Vazio =
caixa vazia, como antes.

Revision ID: 3c7e2a9d5b41
Revises: 8f901beadab1
Create Date: 2026-11-25 10:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3c7e2a9d5b41"
down_revision: str | Sequence[str] | None = "8f901beadab1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column("prompt_template", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("workspaces", "prompt_template")
