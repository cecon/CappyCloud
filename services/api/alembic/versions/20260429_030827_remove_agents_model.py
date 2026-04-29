"""remove_agents_model

Revision ID: 94d6ed5e0f5e
Revises: 20260429_090000
Create Date: 2026-04-29 03:08:27.779929

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "94d6ed5e0f5e"
down_revision: Union[str, Sequence[str], None] = "20260429_090000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove selectable agent/persona model from the product schema."""
    op.execute("ALTER TABLE skills DROP CONSTRAINT IF EXISTS skills_agent_id_fkey")
    op.execute("DROP INDEX IF EXISTS ix_skills_agent_id")
    op.execute("ALTER TABLE skills DROP COLUMN IF EXISTS agent_id")

    op.execute("ALTER TABLE conversations DROP CONSTRAINT IF EXISTS conversations_agent_id_fkey")
    op.execute("DROP INDEX IF EXISTS ix_conversations_agent_id")
    op.execute("ALTER TABLE conversations DROP COLUMN IF EXISTS agent_id")

    op.execute("DROP TABLE IF EXISTS user_agent_profiles CASCADE")
    op.execute("DROP TABLE IF EXISTS agents CASCADE")


def downgrade() -> None:
    """Recreate the legacy agent/persona schema."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agents (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            slug          VARCHAR(128) NOT NULL UNIQUE,
            name          VARCHAR(256) NOT NULL,
            description   TEXT NOT NULL DEFAULT '',
            icon          VARCHAR(64) NOT NULL DEFAULT 'support_agent',
            system_prompt TEXT NOT NULL DEFAULT '',
            default_model VARCHAR(256),
            active        BOOLEAN NOT NULL DEFAULT TRUE,
            owner_id      UUID REFERENCES users(id) ON DELETE SET NULL,
            is_default    BOOLEAN NOT NULL DEFAULT FALSE,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_agents_slug ON agents(slug)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agents_active ON agents(active)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agents_owner_id ON agents(owner_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agents_is_default ON agents(is_default)")

    op.execute("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS agent_id UUID")
    op.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE conversations
            ADD CONSTRAINT conversations_agent_id_fkey
            FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE SET NULL;
        EXCEPTION WHEN duplicate_object THEN
            NULL;
        END $$;
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_conversations_agent_id ON conversations(agent_id)")

    op.execute("ALTER TABLE skills ADD COLUMN IF NOT EXISTS agent_id UUID")
    op.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE skills
            ADD CONSTRAINT skills_agent_id_fkey
            FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE;
        EXCEPTION WHEN duplicate_object THEN
            NULL;
        END $$;
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_skills_agent_id ON skills(agent_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_agent_profiles (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            agent_id   UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            persona    VARCHAR(32) NOT NULL,
            is_default BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_user_agent_profiles_user_persona UNIQUE (user_id, persona)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_user_agent_profiles_user_id ON user_agent_profiles(user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_user_agent_profiles_agent_id "
        "ON user_agent_profiles(agent_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_user_agent_profiles_persona ON user_agent_profiles(persona)"
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_user_agent_profiles_default_per_user
        ON user_agent_profiles(user_id)
        WHERE is_default = true
        """
    )
