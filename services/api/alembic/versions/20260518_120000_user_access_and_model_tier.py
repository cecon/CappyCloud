"""user_access_and_model_tier

Cria as 3 tabelas de permissões binárias (ADR-005 §2) e estende o catálogo
LLM (ADR-006) com ``ai_models.tier`` e ``ai_providers.last_synced_at``.

Tabelas novas:
- ``user_sandbox_access(user_id, sandbox_id)`` — UNIQUE composta + FK CASCADE.
- ``user_repository_access(user_id, repository_id)`` — idem.
- ``user_ai_model_access(user_id, ai_model_id)`` — idem.

Presença da linha = tem acesso. Ausência = não tem. ADMIN ignora as 3.

Colunas novas:
- ``ai_models.tier`` (free | paid | unknown) — derivada do preço pelo sync.
- ``ai_providers.last_synced_at`` (timestamp nullable).

Revision ID: a3fad75f8225
Revises: 51d6c60162f9
Create Date: 2026-05-18 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a3fad75f8225"
down_revision: str | Sequence[str] | None = "51d6c60162f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _access_table(name: str, resource_table: str, resource_col: str) -> None:
    """Cria tabela associativa user × <recurso> com FKs CASCADE e UNIQUE."""
    op.create_table(
        name,
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(resource_col, postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name=f"fk_{name}_user"
        ),
        sa.ForeignKeyConstraint(
            [resource_col],
            [f"{resource_table}.id"],
            ondelete="CASCADE",
            name=f"fk_{name}_{resource_col[:-3]}",
        ),
        sa.UniqueConstraint("user_id", resource_col, name=f"uq_{name}"),
    )
    op.create_index(f"ix_{name}_user_id", name, ["user_id"])
    op.create_index(f"ix_{name}_{resource_col}", name, [resource_col])


def upgrade() -> None:
    """Upgrade schema."""
    _access_table("user_sandbox_access", "sandboxes", "sandbox_id")
    _access_table("user_repository_access", "repositories", "repository_id")
    _access_table("user_ai_model_access", "ai_models", "ai_model_id")

    # tier ('free' | 'paid' | 'unknown') derivado pelo sync.
    op.add_column(
        "ai_models",
        sa.Column(
            "tier",
            sa.String(length=16),
            nullable=False,
            server_default="unknown",
            index=True,
        ),
    )
    op.create_index("ix_ai_models_tier", "ai_models", ["tier"], if_not_exists=True)

    # last_synced_at no provider.
    op.add_column(
        "ai_providers",
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("ai_providers", "last_synced_at")
    op.drop_index("ix_ai_models_tier", table_name="ai_models", if_exists=True)
    op.drop_column("ai_models", "tier")
    for name in ("user_ai_model_access", "user_repository_access", "user_sandbox_access"):
        op.drop_index(
            f"ix_{name}_{name.split('_')[1]}_id"
            if name == "user_sandbox_access"
            else f"ix_{name}_repository_id"
            if name == "user_repository_access"
            else f"ix_{name}_ai_model_id",
            table_name=name,
        )
        op.drop_index(f"ix_{name}_user_id", table_name=name)
        op.drop_table(name)
