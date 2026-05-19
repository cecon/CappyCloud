"""global_skills_catalog_assignments

Revision ID: 8be30de4b8ae
Revises: aedb56ce8bf4
Create Date: 2026-05-18 14:03:59.760061

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "8be30de4b8ae"
down_revision: str | Sequence[str] | None = "aedb56ce8bf4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "global_skills",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_global_skills_name", "global_skills", ["name"], unique=True)

    op.create_table(
        "global_skill_sandboxes",
        sa.Column("skill_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sandbox_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["global_skills.id"],
            ondelete="CASCADE",
            name="fk_global_skill_sandboxes_skill",
        ),
        sa.ForeignKeyConstraint(
            ["sandbox_id"],
            ["sandboxes.id"],
            ondelete="CASCADE",
            name="fk_global_skill_sandboxes_sandbox",
        ),
        sa.PrimaryKeyConstraint("skill_id", "sandbox_id"),
        sa.UniqueConstraint("skill_id", "sandbox_id", name="uq_global_skill_sandbox"),
    )
    op.create_index(
        "ix_global_skill_sandboxes_sandbox_id",
        "global_skill_sandboxes",
        ["sandbox_id"],
    )

    # Move registros legados por sandbox para o catalogo global. Quando o
    # mesmo nome existe em mais de uma sandbox, o sufixo do id evita colisao.
    op.execute(
        sa.text(
            """
            WITH legacy AS (
                SELECT
                    id,
                    CASE
                        WHEN COUNT(*) OVER (PARTITION BY name) > 1
                        THEN LEFT(name, 119) || '-' || LEFT(id::text, 8)
                        ELSE name
                    END AS global_name,
                    COALESCE(description, '') AS description,
                    COALESCE(content, '') AS content,
                    COALESCE(enabled, true) AS enabled,
                    COALESCE(created_at, now()) AS created_at,
                    COALESCE(updated_at, now()) AS updated_at
                FROM sandbox_skills
            )
            INSERT INTO global_skills (
                id, name, description, content, enabled, created_at, updated_at
            )
            SELECT
                id, global_name, description, content, enabled, created_at, updated_at
            FROM legacy
            ON CONFLICT (id) DO NOTHING
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO global_skill_sandboxes (skill_id, sandbox_id, created_at)
            SELECT id, sandbox_id, COALESCE(created_at, now())
            FROM sandbox_skills
            ON CONFLICT (skill_id, sandbox_id) DO NOTHING
            """
        )
    )
    op.execute(sa.text("DELETE FROM sandbox_skills"))


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        sa.text(
            """
            WITH rows AS (
                SELECT
                    gs.id,
                    gss.sandbox_id,
                    gs.name,
                    gs.description,
                    gs.content,
                    gs.enabled,
                    gs.created_at,
                    gs.updated_at,
                    ROW_NUMBER() OVER (PARTITION BY gs.id ORDER BY gss.sandbox_id) AS rn
                FROM global_skills gs
                JOIN global_skill_sandboxes gss ON gss.skill_id = gs.id
            )
            INSERT INTO sandbox_skills (
                id, sandbox_id, name, description, content, enabled, created_at, updated_at
            )
            SELECT
                CASE WHEN rn = 1 THEN id ELSE gen_random_uuid() END,
                sandbox_id,
                name,
                description,
                content,
                enabled,
                created_at,
                updated_at
            FROM rows
            ON CONFLICT ON CONSTRAINT uq_sandbox_skills_name DO NOTHING
            """
        )
    )
    op.drop_index("ix_global_skill_sandboxes_sandbox_id", table_name="global_skill_sandboxes")
    op.drop_table("global_skill_sandboxes")
    op.drop_index("ix_global_skills_name", table_name="global_skills")
    op.drop_table("global_skills")
