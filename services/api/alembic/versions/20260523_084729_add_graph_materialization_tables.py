"""add_graph_materialization_tables

Revision ID: bc534248ac67
Revises: d177e4b41f25
Create Date: 2026-05-23 08:47:29.656852

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "bc534248ac67"
down_revision: Union[str, Sequence[str], None] = "d177e4b41f25"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "graph_nodes",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "repo_id",
            sa.UUID(),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("commit_sha", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=True),
        sa.Column("line_start", sa.Integer(), nullable=True),
        sa.Column("line_end", sa.Integer(), nullable=True),
        sa.Column("source_extractor", sa.Text(), nullable=False),
        sa.Column("extractor_version", sa.Text(), nullable=False),
        sa.Column("attrs", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_graph_nodes_repo_commit", "graph_nodes", ["repo_id", "commit_sha"])
    op.create_index("idx_graph_nodes_repo_kind", "graph_nodes", ["repo_id", "kind"])
    op.create_index("idx_graph_nodes_repo_path", "graph_nodes", ["repo_id", "path"])
    op.create_index(
        "idx_graph_nodes_attrs",
        "graph_nodes",
        ["attrs"],
        postgresql_using="gin",
    )

    op.create_table(
        "graph_edges",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "repo_id",
            sa.UUID(),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("commit_sha", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("target_id", sa.Text(), nullable=True),
        sa.Column("target_external", sa.Text(), nullable=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("confidence", sa.Text(), nullable=False, server_default="high"),
        sa.Column("source_extractor", sa.Text(), nullable=False),
        sa.Column("extractor_version", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "target_id IS NOT NULL OR target_external IS NOT NULL",
            name="ck_graph_edges_target_present",
        ),
    )
    op.create_index(
        "idx_graph_edges_unique",
        "graph_edges",
        [
            "repo_id",
            "commit_sha",
            "source_id",
            sa.text("COALESCE(target_id, target_external)"),
            "type",
        ],
        unique=True,
    )
    op.create_index("idx_graph_edges_repo_commit", "graph_edges", ["repo_id", "commit_sha"])
    op.create_index("idx_graph_edges_source", "graph_edges", ["source_id"])
    op.create_index("idx_graph_edges_target", "graph_edges", ["target_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_graph_edges_target", table_name="graph_edges")
    op.drop_index("idx_graph_edges_source", table_name="graph_edges")
    op.drop_index("idx_graph_edges_repo_commit", table_name="graph_edges")
    op.drop_index("idx_graph_edges_unique", table_name="graph_edges")
    op.drop_table("graph_edges")

    op.drop_index("idx_graph_nodes_attrs", table_name="graph_nodes")
    op.drop_index("idx_graph_nodes_repo_path", table_name="graph_nodes")
    op.drop_index("idx_graph_nodes_repo_kind", table_name="graph_nodes")
    op.drop_index("idx_graph_nodes_repo_commit", table_name="graph_nodes")
    op.drop_table("graph_nodes")
