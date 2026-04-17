"""add_env_slug_worktree_branch_path_to_conversations

Revision ID: 4d18192ad762
Revises: 974e4129244e
Create Date: 2026-04-16 23:32:34.989106

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4d18192ad762"
down_revision: Union[str, Sequence[str], None] = "974e4129244e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add env_slug, worktree_branch, worktree_path to conversations."""
    op.add_column("conversations", sa.Column("env_slug", sa.String(128), nullable=True))
    op.add_column("conversations", sa.Column("worktree_branch", sa.String(512), nullable=True))
    op.add_column("conversations", sa.Column("worktree_path", sa.String(512), nullable=True))
    op.create_index("ix_conversations_env_slug", "conversations", ["env_slug"])


def downgrade() -> None:
    """Remove env_slug, worktree_branch, worktree_path from conversations."""
    op.drop_index("ix_conversations_env_slug", table_name="conversations")
    op.drop_column("conversations", "worktree_path")
    op.drop_column("conversations", "worktree_branch")
    op.drop_column("conversations", "env_slug")
