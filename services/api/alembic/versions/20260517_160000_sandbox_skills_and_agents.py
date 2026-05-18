"""sandbox_skills_and_agents

Cria as tabelas ``sandbox_skills`` e ``sandbox_agents`` para skills/subagents
*globais por sandbox* (ADR-004 §5-6). Estas são distintas das skills por
repositório (``skills`` em ``orm_models_agent.py``) — aquelas continuam intactas.

- ``sandbox_skills``: vira pasta ``~/.claude/skills/<name>/SKILL.md`` no container.
- ``sandbox_agents``: vira arquivo ``~/.claude/agents/<name>.md`` (com frontmatter
  YAML name/description/tools/model + body como system prompt).

Revision ID: 51d6c60162f9
Revises: 9a89b0737130
Create Date: 2026-05-17 16:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "51d6c60162f9"
down_revision: str | Sequence[str] | None = "9a89b0737130"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "sandbox_skills",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("sandbox_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["sandbox_id"], ["sandboxes.id"], ondelete="CASCADE", name="fk_sandbox_skills_sandbox"
        ),
        sa.UniqueConstraint("sandbox_id", "name", name="uq_sandbox_skills_name"),
    )
    op.create_index("ix_sandbox_skills_sandbox_id", "sandbox_skills", ["sandbox_id"])

    op.create_table(
        "sandbox_agents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("sandbox_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("system_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("model", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("tools", postgresql.JSONB(), nullable=False, server_default="[]"),
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
        sa.ForeignKeyConstraint(
            ["sandbox_id"], ["sandboxes.id"], ondelete="CASCADE", name="fk_sandbox_agents_sandbox"
        ),
        sa.UniqueConstraint("sandbox_id", "name", name="uq_sandbox_agents_name"),
    )
    op.create_index("ix_sandbox_agents_sandbox_id", "sandbox_agents", ["sandbox_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_sandbox_agents_sandbox_id", table_name="sandbox_agents")
    op.drop_table("sandbox_agents")
    op.drop_index("ix_sandbox_skills_sandbox_id", table_name="sandbox_skills")
    op.drop_table("sandbox_skills")
