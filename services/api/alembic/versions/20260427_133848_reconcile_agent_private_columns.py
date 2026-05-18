"""reconcile_agent_private_columns

Revision ID: 6d6cedaba01b
Revises: a150801ba0db
Create Date: 2026-04-27 13:38:48.470186

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "6d6cedaba01b"
down_revision: Union[str, Sequence[str], None] = "a150801ba0db"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Reconcile agent privacy/default columns for DBs stamped with the orphan revision."""
    if not sa.inspect(op.get_bind()).has_table("agents"):
        return

    op.execute("ALTER TABLE agents ADD COLUMN IF NOT EXISTS owner_id UUID")
    op.execute(
        "ALTER TABLE agents ADD COLUMN IF NOT EXISTS is_default BOOLEAN NOT NULL DEFAULT FALSE"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_agents_owner'
            ) THEN
                ALTER TABLE agents
                    ADD CONSTRAINT fk_agents_owner
                    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE SET NULL;
            END IF;
        END
        $$;
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_agents_owner_id ON agents (owner_id)")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_agents_is_default_unique
        ON agents (is_default)
        WHERE is_default = TRUE
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_agents_is_default_unique")
    op.execute("DROP INDEX IF EXISTS ix_agents_owner_id")
    op.execute("ALTER TABLE agents DROP CONSTRAINT IF EXISTS fk_agents_owner")
    op.execute("ALTER TABLE agents DROP COLUMN IF EXISTS is_default")
    op.execute("ALTER TABLE agents DROP COLUMN IF EXISTS owner_id")
