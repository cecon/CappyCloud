"""bootstrap_agent_execution_tables

Garante as tabelas de execução do agente (CI/CD, diff, routines, PR) no PostgreSQL.

Bases antigas ou restauradas podem estar em ``alembic_version`` = head sem terem
executado o bloco SQL original (ou com tabelas removidas). Este passo é
idempotente (``CREATE TABLE IF NOT EXISTS`` / ``CREATE INDEX IF NOT EXISTS``).

Revision ID: 20260429_090000
Revises: 20260428_120000
Create Date: 2026-04-29 09:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260429_090000"
down_revision: Union[str, Sequence[str], None] = "20260428_120000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
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
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS diff_comments (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id  UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            file_path        TEXT    NOT NULL,
            line             INTEGER NOT NULL,
            content          TEXT    NOT NULL,
            bundled_at       TIMESTAMPTZ,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_diff_comments_conversation_id "
        "ON diff_comments(conversation_id)"
    )

    op.execute(
        """
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
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_routines_created_by ON routines(created_by)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS routine_runs (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            routine_id   UUID NOT NULL REFERENCES routines(id) ON DELETE CASCADE,
            task_id      UUID REFERENCES agent_tasks(id) ON DELETE SET NULL,
            triggered_by VARCHAR(32)  NOT NULL,
            status       VARCHAR(32)  NOT NULL DEFAULT 'pending',
            started_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_routine_runs_routine_id ON routine_runs(routine_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS pr_subscriptions (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id  UUID    NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            repo_slug        VARCHAR(512) NOT NULL,
            pr_number        INTEGER NOT NULL,
            auto_fix_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_pr_subscriptions_conversation_id "
        "ON pr_subscriptions(conversation_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS pr_subscriptions CASCADE")
    op.execute("DROP TABLE IF EXISTS routine_runs CASCADE")
    op.execute("DROP TABLE IF EXISTS routines CASCADE")
    op.execute("DROP TABLE IF EXISTS diff_comments CASCADE")
    op.execute("DROP TABLE IF EXISTS cicd_events CASCADE")
