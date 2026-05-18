"""mcp_servers_by_sandbox

Move ``mcp_servers`` de "por utilizador" para "por sandbox" (ADR-004 §6).

Estratégia de migração de dados existentes:
- Adiciona ``sandbox_id`` como nullable.
- Backfill: associa todas as linhas existentes à sandbox mais antiga
  (``ORDER BY created_at LIMIT 1``). O ADMIN remapeia depois pela UI.
- Se NÃO existir sandbox cadastrada, apaga as linhas órfãs (dado de teste).
- Drop da unique constraint antiga ``uq_mcp_user_name`` e da coluna ``user_id``.
- Nova unique constraint ``uq_mcp_sandbox_name`` em (sandbox_id, name).

Revision ID: 9a89b0737130
Revises: a2bbe767de31
Create Date: 2026-05-17 14:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "9a89b0737130"
down_revision: str | Sequence[str] | None = "a2bbe767de31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()

    # 1. Adiciona sandbox_id nullable.
    op.add_column(
        "mcp_servers",
        sa.Column("sandbox_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )

    # 2. Backfill: pega a sandbox mais antiga e associa todas as linhas.
    fallback_sandbox = bind.execute(
        sa.text("SELECT id FROM sandboxes ORDER BY created_at LIMIT 1")
    ).scalar()

    if fallback_sandbox is not None:
        bind.execute(
            sa.text("UPDATE mcp_servers SET sandbox_id = :sb WHERE sandbox_id IS NULL").bindparams(
                sb=fallback_sandbox
            )
        )
    else:
        # Nenhuma sandbox existe → linhas existentes são órfãs.
        bind.execute(sa.text("DELETE FROM mcp_servers"))

    # 2.1 Deduplica (sandbox_id, name): mantém o mais antigo, descarta o resto.
    # Linhas pré-migração com mesmo nome em users diferentes colidem ao
    # virarem por sandbox; ADMIN re-cadastra os perdidos pela nova UI.
    bind.execute(
        sa.text(
            """
            DELETE FROM mcp_servers
            WHERE id IN (
                SELECT id FROM (
                    SELECT id, ROW_NUMBER() OVER (
                        PARTITION BY sandbox_id, name
                        ORDER BY created_at ASC, id ASC
                    ) AS rn
                    FROM mcp_servers
                ) ranked
                WHERE ranked.rn > 1
            )
            """
        )
    )

    # 3. Trava sandbox_id como NOT NULL.
    op.alter_column("mcp_servers", "sandbox_id", nullable=False)

    # 4. Drop unique (user_id, name) e a coluna user_id (com FK).
    op.drop_constraint("uq_mcp_user_name", "mcp_servers", type_="unique")
    op.drop_index("ix_mcp_servers_user_id", table_name="mcp_servers", if_exists=True)
    op.drop_column("mcp_servers", "user_id")

    # 5. FK + índice + unique novos.
    op.create_foreign_key(
        "fk_mcp_servers_sandbox_id",
        source_table="mcp_servers",
        referent_table="sandboxes",
        local_cols=["sandbox_id"],
        remote_cols=["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_mcp_servers_sandbox_id",
        "mcp_servers",
        ["sandbox_id"],
    )
    op.create_unique_constraint("uq_mcp_sandbox_name", "mcp_servers", ["sandbox_id", "name"])


def downgrade() -> None:
    """Downgrade schema.

    O downgrade é destrutivo (não consegue reconstruir o user_id original) —
    requer truncate da tabela. Mantido para shape de schema; não para dados.
    """
    op.drop_constraint("uq_mcp_sandbox_name", "mcp_servers", type_="unique")
    op.drop_index("ix_mcp_servers_sandbox_id", table_name="mcp_servers")
    op.drop_constraint("fk_mcp_servers_sandbox_id", "mcp_servers", type_="foreignkey")

    # Recoloca user_id como NOT NULL: precisamos apagar as linhas antes.
    op.execute(sa.text("DELETE FROM mcp_servers"))

    op.add_column(
        "mcp_servers",
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.create_foreign_key(
        None,
        source_table="mcp_servers",
        referent_table="users",
        local_cols=["user_id"],
        remote_cols=["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_mcp_servers_user_id", "mcp_servers", ["user_id"])
    op.create_unique_constraint("uq_mcp_user_name", "mcp_servers", ["user_id", "name"])

    op.drop_column("mcp_servers", "sandbox_id")
