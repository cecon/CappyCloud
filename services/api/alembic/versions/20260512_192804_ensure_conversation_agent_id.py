"""ensure_conversation_agent_id

Revision ID: 2e0474891143
Revises: 8272efee3060
Create Date: 2026-05-12 19:28:04.657147

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "2e0474891143"
down_revision: str | Sequence[str] | None = "8272efee3060"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Garante estrutura de agentes em bancos parcialmente migrados."""
    _execute(
        """
        CREATE TABLE IF NOT EXISTS agents (
            id UUID PRIMARY KEY,
            slug VARCHAR(128) NOT NULL,
            name VARCHAR(256) NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            icon VARCHAR(64) NOT NULL DEFAULT 'support_agent',
            system_prompt TEXT NOT NULL DEFAULT '',
            default_model VARCHAR(256),
            active BOOLEAN NOT NULL DEFAULT TRUE,
            owner_id UUID REFERENCES users(id) ON DELETE SET NULL,
            is_default BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    _execute("ALTER TABLE agents ADD COLUMN IF NOT EXISTS owner_id UUID")
    _execute(
        "ALTER TABLE agents ADD COLUMN IF NOT EXISTS is_default BOOLEAN NOT NULL DEFAULT FALSE"
    )
    _execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_agents_owner'
            ) THEN
                ALTER TABLE agents
                    ADD CONSTRAINT fk_agents_owner
                    FOREIGN KEY (owner_id)
                    REFERENCES users(id)
                    ON DELETE SET NULL;
            END IF;
        END $$;
        """
    )
    _execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_agents_slug ON agents(slug)")
    _execute("CREATE INDEX IF NOT EXISTS ix_agents_active ON agents(active)")
    _execute("CREATE INDEX IF NOT EXISTS ix_agents_owner_id ON agents(owner_id)")
    _execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_agents_is_default_unique
            ON agents(is_default)
            WHERE is_default = TRUE
        """
    )

    _execute("ALTER TABLE skills ADD COLUMN IF NOT EXISTS agent_id UUID")
    _execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_skills_agent'
            ) THEN
                ALTER TABLE skills
                    ADD CONSTRAINT fk_skills_agent
                    FOREIGN KEY (agent_id)
                    REFERENCES agents(id)
                    ON DELETE CASCADE;
            END IF;
        END $$;
        """
    )
    _execute("CREATE INDEX IF NOT EXISTS ix_skills_agent_id ON skills(agent_id)")

    _execute("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS agent_id UUID")
    _execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_conversations_agent'
            ) THEN
                ALTER TABLE conversations
                    ADD CONSTRAINT fk_conversations_agent
                    FOREIGN KEY (agent_id)
                    REFERENCES agents(id)
                    ON DELETE SET NULL;
            END IF;
        END $$;
        """
    )
    _execute("CREATE INDEX IF NOT EXISTS ix_conversations_agent_id ON conversations(agent_id)")

    _execute(
        """
        CREATE TABLE IF NOT EXISTS user_agent_profiles (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            persona VARCHAR(32) NOT NULL,
            is_default BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_user_agent_profiles_user_persona UNIQUE (user_id, persona)
        )
        """
    )
    _execute(
        "CREATE INDEX IF NOT EXISTS ix_user_agent_profiles_user_id ON user_agent_profiles(user_id)"
    )
    _execute(
        "CREATE INDEX IF NOT EXISTS ix_user_agent_profiles_agent_id ON user_agent_profiles(agent_id)"
    )
    _execute(
        "CREATE INDEX IF NOT EXISTS ix_user_agent_profiles_persona ON user_agent_profiles(persona)"
    )
    _execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_user_agent_profiles_default_per_user
            ON user_agent_profiles(user_id)
            WHERE is_default = TRUE
        """
    )


def downgrade() -> None:
    """Remove reparo de agent_id em conversations."""
    _execute("DROP INDEX IF EXISTS uq_user_agent_profiles_default_per_user")
    _execute("DROP TABLE IF EXISTS user_agent_profiles")
    _execute("DROP INDEX IF EXISTS ix_conversations_agent_id")
    _execute(
        """
        ALTER TABLE conversations
            DROP CONSTRAINT IF EXISTS fk_conversations_agent,
            DROP COLUMN IF EXISTS agent_id
        """
    )
    _execute("DROP INDEX IF EXISTS ix_skills_agent_id")
    _execute(
        """
        ALTER TABLE skills
            DROP CONSTRAINT IF EXISTS fk_skills_agent,
            DROP COLUMN IF EXISTS agent_id
        """
    )
    _execute("DROP INDEX IF EXISTS ix_agents_is_default_unique")
    _execute("DROP INDEX IF EXISTS ix_agents_owner_id")
    _execute("DROP INDEX IF EXISTS ix_agents_active")
    _execute("DROP INDEX IF EXISTS ix_agents_slug")
    _execute("DROP TABLE IF EXISTS agents")


def _execute(sql: str) -> None:
    op.execute(sa.text(sql))
