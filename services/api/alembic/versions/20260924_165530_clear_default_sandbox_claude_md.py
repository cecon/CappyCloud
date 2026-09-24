"""clear default sandbox claude md

As regras padrão do agente passaram a vir da imagem (``sandbox/CLAUDE.md``) e o
campo ``sandboxes.claude_md`` virou só "instruções extras", somadas a elas. Os
textos padrão gravados antes no campo (seed de b6fbc5d81584 e a versão aplicada
à mão em 2026-09-24) duplicariam a base e são limpos.

Revision ID: 7858fdf18f45
Revises: ff3bc9b4993d
Create Date: 2026-09-24 16:55:30.425335

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7858fdf18f45"
down_revision: str | Sequence[str] | None = "ff3bc9b4993d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DEFAULT_HEADINGS = (
    "# Sandbox — Global Skills Reference%",
    "# Regras do agente (CappyCloud)%",
)


def upgrade() -> None:
    for heading in _DEFAULT_HEADINGS:
        op.execute(
            sa.text("UPDATE sandboxes SET claude_md = '' WHERE claude_md LIKE :heading").bindparams(
                heading=heading
            )
        )


def downgrade() -> None:
    # Os textos antigos não são restaurados: a base da imagem os substitui.
    pass
