"""add_worktree_and_pr_columns_to_conversations

Revision ID: 624ac0a076cb
Revises: 187cb053ca60
Create Date: 2026-04-19 21:23:09

"""

from typing import Sequence, Union

from alembic import op

revision: str = "624ac0a076cb"
down_revision: Union[str, Sequence[str], None] = "187cb053ca60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE conversations
            ADD COLUMN IF NOT EXISTS worktree_exists  BOOLEAN      NOT NULL DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS lines_added      INTEGER      NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS lines_removed    INTEGER      NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS files_changed    INTEGER      NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS pr_url           TEXT,
            ADD COLUMN IF NOT EXISTS pr_status        VARCHAR(32)  NOT NULL DEFAULT 'none',
            ADD COLUMN IF NOT EXISTS pr_approved      BOOLEAN      NOT NULL DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS ci_status        VARCHAR(32)  NOT NULL DEFAULT 'unknown',
            ADD COLUMN IF NOT EXISTS ci_url           TEXT,
            ADD COLUMN IF NOT EXISTS github_pr_number INTEGER,
            ADD COLUMN IF NOT EXISTS github_repo_slug VARCHAR(512)
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE conversations
            DROP COLUMN IF EXISTS worktree_exists,
            DROP COLUMN IF EXISTS lines_added,
            DROP COLUMN IF EXISTS lines_removed,
            DROP COLUMN IF EXISTS files_changed,
            DROP COLUMN IF EXISTS pr_url,
            DROP COLUMN IF EXISTS pr_status,
            DROP COLUMN IF EXISTS pr_approved,
            DROP COLUMN IF EXISTS ci_status,
            DROP COLUMN IF EXISTS ci_url,
            DROP COLUMN IF EXISTS github_pr_number,
            DROP COLUMN IF EXISTS github_repo_slug
    """)
