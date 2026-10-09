"""add workspace report themes

Temas do relatório de uso por workspace: modelo pronto (``report_theme_preset``)
e regras próprias em JSON (``report_themes``). O proteus nasce com o modelo
Protheus/TSS (formato da Diretoria); os demais usam o genérico até o super admin escolher.

Revision ID: 54191f35ea27
Revises: 8ed57121871e
Create Date: 2026-10-09 14:48:55.415605

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "54191f35ea27"
down_revision: str | Sequence[str] | None = "8ed57121871e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("workspaces", sa.Column("report_theme_preset", sa.String(64), nullable=True))
    op.add_column(
        "workspaces",
        sa.Column("report_themes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.execute("UPDATE workspaces SET report_theme_preset = 'protheus-tss' WHERE slug = 'proteus'")


def downgrade() -> None:
    op.drop_column("workspaces", "report_themes")
    op.drop_column("workspaces", "report_theme_preset")
