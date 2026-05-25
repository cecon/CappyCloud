"""add graph reconciliation runs

Revision ID: 5d8dd85798ce
Revises: bc534248ac67
Create Date: 2026-05-23 14:02:08.325514

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "5d8dd85798ce"
down_revision: Union[str, Sequence[str], None] = "bc534248ac67"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
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


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "idx_graph_reconciliation_runs_repo_commit_created",
        table_name="graph_reconciliation_runs",
    )
    op.drop_table("graph_reconciliation_runs")
