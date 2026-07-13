"""add_document_graph

Revision ID: 0870d5b25ab2
Revises: 03564da620ed
Create Date: 2026-07-10 19:05:09.106323

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0870d5b25ab2"
down_revision: Union[str, Sequence[str], None] = "03564da620ed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "document_graph_nodes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("repository_id", sa.UUID(), nullable=False),
        sa.Column("node_key", sa.String(length=512), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("attrs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "node_key",
            name="uq_document_graph_nodes_doc_key",
        ),
    )
    op.create_index(
        "idx_document_graph_nodes_name",
        "document_graph_nodes",
        ["name"],
    )
    op.create_index(
        "idx_document_graph_nodes_repo_kind",
        "document_graph_nodes",
        ["repository_id", "kind"],
    )
    op.create_index(
        op.f("ix_document_graph_nodes_document_id"),
        "document_graph_nodes",
        ["document_id"],
    )
    op.create_index(
        op.f("ix_document_graph_nodes_repository_id"),
        "document_graph_nodes",
        ["repository_id"],
    )

    op.create_table(
        "document_graph_edges",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("repository_id", sa.UUID(), nullable=False),
        sa.Column("source_node_id", sa.UUID(), nullable=False),
        sa.Column("target_node_id", sa.UUID(), nullable=True),
        sa.Column("target_key", sa.String(length=512), nullable=True),
        sa.Column("edge_type", sa.String(length=64), nullable=False),
        sa.Column("attrs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_node_id"],
            ["document_graph_nodes.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_node_id"],
            ["document_graph_nodes.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "source_node_id",
            "target_node_id",
            "target_key",
            "edge_type",
            name="uq_document_graph_edges_doc_relation",
        ),
    )
    op.create_index(
        "idx_document_graph_edges_repo_type",
        "document_graph_edges",
        ["repository_id", "edge_type"],
    )
    op.create_index(
        "idx_document_graph_edges_target_key",
        "document_graph_edges",
        ["target_key"],
    )
    op.create_index(
        op.f("ix_document_graph_edges_document_id"),
        "document_graph_edges",
        ["document_id"],
    )
    op.create_index(
        op.f("ix_document_graph_edges_repository_id"),
        "document_graph_edges",
        ["repository_id"],
    )
    op.create_index(
        op.f("ix_document_graph_edges_source_node_id"),
        "document_graph_edges",
        ["source_node_id"],
    )
    op.create_index(
        op.f("ix_document_graph_edges_target_node_id"),
        "document_graph_edges",
        ["target_node_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_document_graph_edges_target_node_id"),
        table_name="document_graph_edges",
    )
    op.drop_index(
        op.f("ix_document_graph_edges_source_node_id"),
        table_name="document_graph_edges",
    )
    op.drop_index(
        op.f("ix_document_graph_edges_repository_id"),
        table_name="document_graph_edges",
    )
    op.drop_index(
        op.f("ix_document_graph_edges_document_id"),
        table_name="document_graph_edges",
    )
    op.drop_index("idx_document_graph_edges_target_key", table_name="document_graph_edges")
    op.drop_index("idx_document_graph_edges_repo_type", table_name="document_graph_edges")
    op.drop_table("document_graph_edges")

    op.drop_index(
        op.f("ix_document_graph_nodes_repository_id"),
        table_name="document_graph_nodes",
    )
    op.drop_index(
        op.f("ix_document_graph_nodes_document_id"),
        table_name="document_graph_nodes",
    )
    op.drop_index("idx_document_graph_nodes_repo_kind", table_name="document_graph_nodes")
    op.drop_index("idx_document_graph_nodes_name", table_name="document_graph_nodes")
    op.drop_table("document_graph_nodes")
