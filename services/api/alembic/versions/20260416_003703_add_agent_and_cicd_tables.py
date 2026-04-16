"""add_agent_and_cicd_tables

Revision ID: 974e4129244e
Revises:
Create Date: 2026-04-16 00:37:03.224340

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "974e4129244e"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Creates all base tables (users, repo_environments, conversations, messages)
    plus new agent execution, CI/CD, diff-comments, routines and PR-subscription tables.
    """
    # ------------------------------------------------------------------ #
    # Base tables (idempotent — use IF NOT EXISTS so existing DBs are safe)
    # ------------------------------------------------------------------ #
    op.execute("""
        CREATE TABLE IF NOT EXISTS repo_environments (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            slug        VARCHAR(128) NOT NULL UNIQUE,
            name        VARCHAR(256) NOT NULL,
            repo_url    TEXT NOT NULL,
            branch      VARCHAR(256) NOT NULL DEFAULT 'main',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email            VARCHAR(320) NOT NULL UNIQUE,
            hashed_password  VARCHAR(255) NOT NULL,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id          UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            environment_id   UUID REFERENCES repo_environments(id) ON DELETE SET NULL,
            title            VARCHAR(512) NOT NULL DEFAULT 'Nova conversa',
            base_branch      VARCHAR(255),
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id  UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            role             VARCHAR(32) NOT NULL,
            content          TEXT NOT NULL,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ------------------------------------------------------------------ #
    # Incremental columns on conversations (safe on existing DBs)
    # ------------------------------------------------------------------ #
    op.execute("""
        ALTER TABLE conversations
        ADD COLUMN IF NOT EXISTS github_pr_number INTEGER,
        ADD COLUMN IF NOT EXISTS github_repo_slug  VARCHAR(512)
    """)

    # ------------------------------------------------------------------ #
    # Indexes on base tables (idempotent)
    # ------------------------------------------------------------------ #
    op.execute("CREATE INDEX IF NOT EXISTS ix_repo_environments_slug ON repo_environments(slug)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_email ON users(email)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_conversations_user_id ON conversations(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_conversations_environment_id ON conversations(environment_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_messages_conversation_id ON messages(conversation_id)")

    # ------------------------------------------------------------------ #
    # agent_tasks
    # ------------------------------------------------------------------ #
    op.execute("""
        CREATE TABLE IF NOT EXISTS agent_tasks (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id  UUID REFERENCES conversations(id) ON DELETE SET NULL,
            env_slug         VARCHAR(128) NOT NULL,
            session_id       VARCHAR(256) NOT NULL DEFAULT '',
            status           VARCHAR(32)  NOT NULL DEFAULT 'pending',
            triggered_by     VARCHAR(32)  NOT NULL DEFAULT 'user',
            trigger_payload  JSONB        NOT NULL DEFAULT '{}',
            prompt           TEXT         NOT NULL,
            started_at       TIMESTAMPTZ,
            completed_at     TIMESTAMPTZ,
            last_event_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_tasks_conversation_id ON agent_tasks(conversation_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_tasks_env_slug ON agent_tasks(env_slug)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_tasks_status ON agent_tasks(status)")

    # ------------------------------------------------------------------ #
    # agent_events
    # ------------------------------------------------------------------ #
    op.execute("""
        CREATE TABLE IF NOT EXISTS agent_events (
            id          BIGSERIAL PRIMARY KEY,
            task_id     UUID NOT NULL REFERENCES agent_tasks(id) ON DELETE CASCADE,
            event_type  VARCHAR(64) NOT NULL,
            data        JSONB       NOT NULL DEFAULT '{}',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_events_task_id_id ON agent_events(task_id, id)")

    # ------------------------------------------------------------------ #
    # cicd_events
    # ------------------------------------------------------------------ #
    op.execute("""
        CREATE TABLE IF NOT EXISTS cicd_events (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source       VARCHAR(32)  NOT NULL,
            event_type   VARCHAR(128) NOT NULL,
            repo_slug    VARCHAR(512),
            payload      JSONB        NOT NULL DEFAULT '{}',
            task_id      UUID REFERENCES agent_tasks(id) ON DELETE SET NULL,
            processed_at TIMESTAMPTZ,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ------------------------------------------------------------------ #
    # diff_comments
    # ------------------------------------------------------------------ #
    op.execute("""
        CREATE TABLE IF NOT EXISTS diff_comments (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id  UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            file_path        TEXT    NOT NULL,
            line             INTEGER NOT NULL,
            content          TEXT    NOT NULL,
            bundled_at       TIMESTAMPTZ,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_diff_comments_conversation_id ON diff_comments(conversation_id)")

    # ------------------------------------------------------------------ #
    # routines
    # ------------------------------------------------------------------ #
    op.execute("""
        CREATE TABLE IF NOT EXISTS routines (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name            VARCHAR(256) NOT NULL,
            prompt          TEXT         NOT NULL,
            env_slug        VARCHAR(128) NOT NULL REFERENCES repo_environments(slug) ON DELETE SET NULL,
            triggers        JSONB        NOT NULL DEFAULT '[]',
            enabled         BOOLEAN      NOT NULL DEFAULT TRUE,
            created_by      UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            api_token_hash  VARCHAR(256),
            created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            last_run_at     TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_routines_created_by ON routines(created_by)")

    # ------------------------------------------------------------------ #
    # routine_runs
    # ------------------------------------------------------------------ #
    op.execute("""
        CREATE TABLE IF NOT EXISTS routine_runs (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            routine_id   UUID NOT NULL REFERENCES routines(id) ON DELETE CASCADE,
            task_id      UUID REFERENCES agent_tasks(id) ON DELETE SET NULL,
            triggered_by VARCHAR(32)  NOT NULL,
            status       VARCHAR(32)  NOT NULL DEFAULT 'pending',
            started_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_routine_runs_routine_id ON routine_runs(routine_id)")

    # ------------------------------------------------------------------ #
    # pr_subscriptions
    # ------------------------------------------------------------------ #
    op.execute("""
        CREATE TABLE IF NOT EXISTS pr_subscriptions (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id  UUID    NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            repo_slug        VARCHAR(512) NOT NULL,
            pr_number        INTEGER NOT NULL,
            auto_fix_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_pr_subscriptions_conversation_id ON pr_subscriptions(conversation_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_pr_subscriptions_repo_pr ON pr_subscriptions(repo_slug, pr_number)")


def downgrade() -> None:
    """Downgrade schema — removes all agent/cicd tables and added columns."""
    op.execute("DROP TABLE IF EXISTS pr_subscriptions CASCADE")
    op.execute("DROP TABLE IF EXISTS routine_runs CASCADE")
    op.execute("DROP TABLE IF EXISTS routines CASCADE")
    op.execute("DROP TABLE IF EXISTS diff_comments CASCADE")
    op.execute("DROP TABLE IF EXISTS cicd_events CASCADE")
    op.execute("DROP TABLE IF EXISTS agent_events CASCADE")
    op.execute("DROP TABLE IF EXISTS agent_tasks CASCADE")
    op.execute("""
        ALTER TABLE conversations
        DROP COLUMN IF EXISTS github_pr_number,
        DROP COLUMN IF EXISTS github_repo_slug
    """)
    op.execute("DROP TABLE IF EXISTS messages CASCADE")
    op.execute("DROP TABLE IF EXISTS conversations CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
    op.execute("DROP TABLE IF EXISTS repo_environments CASCADE")

