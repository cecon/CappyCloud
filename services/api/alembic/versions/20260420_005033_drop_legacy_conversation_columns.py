"""drop_legacy_conversation_columns

Revision ID: 4706bb4e7c11
Revises: 624ac0a076cb
Create Date: 2026-04-20 00:50:33.026636

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4706bb4e7c11"
down_revision: Union[str, Sequence[str], None] = "624ac0a076cb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotente: bases já migradas parcialmente ou sem estas colunas não rebentam.
    op.execute(sa.text("DROP INDEX IF EXISTS ix_conversations_env_slug"))
    op.execute(sa.text("DROP INDEX IF EXISTS ix_conversations_environment_id"))
    for col in ("environment_id", "base_branch", "env_slug", "worktree_branch", "worktree_path"):
        op.execute(sa.text(f'ALTER TABLE conversations DROP COLUMN IF EXISTS "{col}"'))
    for col in ("env_slug", "container_id", "worktree_path"):
        op.execute(sa.text(f'ALTER TABLE cappy_sessions DROP COLUMN IF EXISTS "{col}"'))


def downgrade() -> None:
    # cappy_sessions
    op.add_column("cappy_sessions", sa.Column("worktree_path", sa.Text(), nullable=True))
    op.add_column("cappy_sessions", sa.Column("container_id", sa.Text(), nullable=True))
    op.add_column("cappy_sessions", sa.Column("env_slug", sa.String(128), nullable=True))

    # conversations
    op.add_column("conversations", sa.Column("worktree_path", sa.String(512), nullable=True))
    op.add_column("conversations", sa.Column("worktree_branch", sa.String(512), nullable=True))
    op.add_column("conversations", sa.Column("env_slug", sa.String(128), nullable=True))
    op.add_column("conversations", sa.Column("base_branch", sa.String(255), nullable=True))
    op.add_column("conversations", sa.Column("environment_id", sa.UUID(), nullable=True))
    op.create_index("ix_conversations_env_slug", "conversations", ["env_slug"])
    op.create_index("ix_conversations_environment_id", "conversations", ["environment_id"])
