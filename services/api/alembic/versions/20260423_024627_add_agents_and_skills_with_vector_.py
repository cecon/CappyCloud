"""add_agents_and_skills_with_vector_embedding

Revision ID: e574cbd3e4fe
Revises: 4706bb4e7c11
Create Date: 2026-04-23 02:46:27.401481

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "e574cbd3e4fe"
down_revision: Union[str, Sequence[str], None] = "4706bb4e7c11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Garante extensão pgvector (idempotente).
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))

    # ── agents ────────────────────────────────────────────────
    op.create_table(
        "agents",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("icon", sa.String(length=64), nullable=False, server_default="support_agent"),
        sa.Column("system_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("default_model", sa.String(length=256), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_agents_slug", "agents", ["slug"], unique=True)
    op.create_index("ix_agents_active", "agents", ["active"])

    # ── skills ────────────────────────────────────────────────
    op.create_table(
        "skills",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "agent_id",
            sa.UUID(),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("slug", sa.String(length=256), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "tags",
            sa.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_skills_slug", "skills", ["slug"])
    op.create_index("ix_skills_agent_id", "skills", ["agent_id"])
    op.create_index("ix_skills_active", "skills", ["active"])
    # Índice HNSW para busca por similaridade cosseno.
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_skills_embedding_hnsw "
            "ON skills USING hnsw (embedding vector_cosine_ops)"
        )
    )

    # ── conversations.agent_id ────────────────────────────────
    op.add_column(
        "conversations",
        sa.Column("agent_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_conversations_agent",
        "conversations",
        "agents",
        ["agent_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_conversations_agent_id", "conversations", ["agent_id"])


def downgrade() -> None:
    op.drop_index("ix_conversations_agent_id", table_name="conversations")
    op.drop_constraint("fk_conversations_agent", "conversations", type_="foreignkey")
    op.drop_column("conversations", "agent_id")

    op.execute(sa.text("DROP INDEX IF EXISTS ix_skills_embedding_hnsw"))
    op.drop_index("ix_skills_active", table_name="skills")
    op.drop_index("ix_skills_agent_id", table_name="skills")
    op.drop_index("ix_skills_slug", table_name="skills")
    op.drop_table("skills")

    op.drop_index("ix_agents_active", table_name="agents")
    op.drop_index("ix_agents_slug", table_name="agents")
    op.drop_table("agents")
