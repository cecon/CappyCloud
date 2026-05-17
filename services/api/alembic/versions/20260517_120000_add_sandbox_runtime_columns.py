"""add_sandbox_runtime_columns

Adiciona campos ao ``sandboxes`` para suportar cadastro como entidade real:
- ``runtime``: orquestrador (compose | swarm) — ADR-004.
- ``image``: imagem Docker que o adapter usa ao criar o container.
- ``env_vars``: variáveis de ambiente injetadas no container (JSONB).
- ``container_status``: estado do container no orquestrador (ADR-004 §3).

O campo ``status`` existente (active|draining|offline) continua representando
o status *lógico* da sandbox; ``container_status`` é o estado *físico*.

Revision ID: a2bbe767de31
Revises: 3ae071e0df36
Create Date: 2026-05-17 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a2bbe767de31"
down_revision: str | Sequence[str] | None = "3ae071e0df36"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "sandboxes",
        sa.Column(
            "runtime",
            sa.String(length=32),
            nullable=False,
            server_default="compose",
        ),
    )
    op.add_column(
        "sandboxes",
        sa.Column("image", sa.String(length=512), nullable=False, server_default=""),
    )
    op.add_column(
        "sandboxes",
        sa.Column(
            "env_vars",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "sandboxes",
        sa.Column(
            "container_status",
            sa.String(length=32),
            nullable=False,
            server_default="not_created",
            index=True,
        ),
    )
    op.create_index(
        "ix_sandboxes_container_status",
        "sandboxes",
        ["container_status"],
        if_not_exists=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_sandboxes_container_status", table_name="sandboxes", if_exists=True)
    op.drop_column("sandboxes", "container_status")
    op.drop_column("sandboxes", "env_vars")
    op.drop_column("sandboxes", "image")
    op.drop_column("sandboxes", "runtime")
