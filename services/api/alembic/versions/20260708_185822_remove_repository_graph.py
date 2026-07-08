"""remove repository graph

Revision ID: 03564da620ed
Revises: 20260708_170000
Create Date: 2026-07-08 18:58:22.554780

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "03564da620ed"
down_revision: Union[str, Sequence[str], None] = "20260708_170000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        DELETE FROM sandbox_sync_queue
        WHERE operation IN (
            'materialize_repo_graph',
            'reconcile_repo_graph',
            'doc_import_for_document'
        )
        """
    )
    op.drop_table("graph_reconciliation_runs")
    op.drop_table("graph_edges")
    op.drop_table("graph_nodes")
    op.drop_column("mcp_tool_invocations", "materialized")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "mcp_tool_invocations",
        sa.Column("materialized", sa.Boolean(), nullable=True),
    )

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

    op.create_table(
        "graph_reconciliation_runs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "repo_id",
            sa.UUID(),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("commit_sha", sa.Text(), nullable=False),
        sa.Column("extractor_version", sa.Text(), nullable=False),
        sa.Column("llm_model", sa.Text(), nullable=True),
        sa.Column("mode", sa.Text(), nullable=False, server_default="all"),
        sa.Column("summary", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("unresolved", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_graph_reconciliation_runs_repo_commit_created",
        "graph_reconciliation_runs",
        ["repo_id", "commit_sha", "created_at"],
    )
