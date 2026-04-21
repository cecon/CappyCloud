"""add_platform_tables_and_seed_sandbox

Revision ID: 187cb053ca60
Revises: 72cdc895ab1c
Create Date: 2026-04-19 19:17:34.933190

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "187cb053ca60"
down_revision: Union[str, Sequence[str], None] = "72cdc895ab1c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cria tabelas da plataforma e insere sandbox padrão.

    Todas as operações são idempotentes (IF NOT EXISTS / ON CONFLICT DO NOTHING)
    para que possam rodar em bancos que já possuam parte das tabelas via SQL seed.
    """
    # ── sandboxes ────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS sandboxes (
            id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            name         VARCHAR(128) UNIQUE NOT NULL,
            host         VARCHAR(256) NOT NULL,
            grpc_port    INTEGER     NOT NULL DEFAULT 50051,
            session_port INTEGER     NOT NULL DEFAULT 8080,
            status       VARCHAR(32) NOT NULL DEFAULT 'active',
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_sandboxes_name   ON sandboxes(name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sandboxes_status ON sandboxes(status)")

    # sandbox padrão
    op.execute("""
        INSERT INTO sandboxes (name, host, grpc_port, session_port, status)
        VALUES ('cappycloud-sandbox', 'cappycloud-sandbox', 50051, 8080, 'active')
        ON CONFLICT (name) DO NOTHING
    """)

    # ── git_providers ─────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS git_providers (
            id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            name             VARCHAR(128) NOT NULL,
            provider_type    VARCHAR(32)  NOT NULL DEFAULT 'github',
            base_url         TEXT        NOT NULL DEFAULT '',
            org_or_project   TEXT        NOT NULL DEFAULT '',
            token_encrypted  TEXT        NOT NULL DEFAULT '',
            active           BOOLEAN     NOT NULL DEFAULT TRUE,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_git_providers_type ON git_providers(provider_type)")

    # ── ai_providers ──────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS ai_providers (
            id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            name              VARCHAR(128) UNIQUE NOT NULL,
            base_url          TEXT        NOT NULL DEFAULT 'https://openrouter.ai/api/v1',
            api_key_encrypted TEXT        NOT NULL DEFAULT '',
            active            BOOLEAN     NOT NULL DEFAULT TRUE,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ── ai_models ─────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS ai_models (
            id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            provider_id    UUID        NOT NULL REFERENCES ai_providers(id) ON DELETE CASCADE,
            model_id       VARCHAR(256) NOT NULL,
            display_name   VARCHAR(256) NOT NULL,
            capabilities   JSONB       NOT NULL DEFAULT '["text"]',
            is_default     JSONB       NOT NULL DEFAULT '{}',
            context_window INTEGER     NOT NULL DEFAULT 200000,
            active         BOOLEAN     NOT NULL DEFAULT TRUE,
            created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_ai_models_provider ON ai_models(provider_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ai_models_active   ON ai_models(active)")

    # ── repositories ──────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS repositories (
            id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            slug            VARCHAR(128) UNIQUE NOT NULL,
            name            VARCHAR(256) NOT NULL,
            provider_id     UUID        REFERENCES git_providers(id) ON DELETE SET NULL,
            clone_url       TEXT        NOT NULL,
            default_branch  VARCHAR(256) NOT NULL DEFAULT 'main',
            sandbox_id      UUID        REFERENCES sandboxes(id) ON DELETE SET NULL,
            sandbox_status  VARCHAR(32) NOT NULL DEFAULT 'not_cloned',
            sandbox_path    TEXT        NOT NULL DEFAULT '',
            last_sync_at    TIMESTAMPTZ,
            error_message   TEXT,
            active          BOOLEAN     NOT NULL DEFAULT TRUE,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_repositories_sandbox_id     ON repositories(sandbox_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_repositories_sandbox_status ON repositories(sandbox_status)"
    )

    # ── sandbox_sync_queue ────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS sandbox_sync_queue (
            id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            sandbox_id   UUID        NOT NULL REFERENCES sandboxes(id) ON DELETE CASCADE,
            operation    VARCHAR(64) NOT NULL,
            payload      JSONB       NOT NULL DEFAULT '{}',
            priority     INTEGER     NOT NULL DEFAULT 5,
            status       VARCHAR(32) NOT NULL DEFAULT 'pending',
            retries      INTEGER     NOT NULL DEFAULT 0,
            last_error   TEXT,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            processed_at TIMESTAMPTZ
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sandbox_sync_queue_sandbox ON sandbox_sync_queue(sandbox_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sandbox_sync_queue_status  ON sandbox_sync_queue(status)"
    )

    # ── conversations: colunas adicionadas pelo 01-sandbox-multi-repo.sql ────
    op.execute("""
        ALTER TABLE conversations
            ADD COLUMN IF NOT EXISTS repos            JSONB        NOT NULL DEFAULT '[]',
            ADD COLUMN IF NOT EXISTS session_root     TEXT,
            ADD COLUMN IF NOT EXISTS sandbox_id       UUID         REFERENCES sandboxes(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS ai_model_id      UUID         REFERENCES ai_models(id) ON DELETE SET NULL,
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
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_conversations_sandbox_id ON conversations(sandbox_id)"
    )

    # ── agent_tasks: coluna sandbox_id ────────────────────────────────────────
    op.execute("""
        ALTER TABLE agent_tasks
            ADD COLUMN IF NOT EXISTS sandbox_id UUID REFERENCES sandboxes(id) ON DELETE SET NULL
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_tasks_sandbox_id ON agent_tasks(sandbox_id)")


def downgrade() -> None:
    """Remove tabelas da plataforma criadas nesta migration."""
    op.execute("ALTER TABLE agent_tasks      DROP COLUMN IF EXISTS sandbox_id")
    op.execute("""
        ALTER TABLE conversations
            DROP COLUMN IF EXISTS sandbox_id,
            DROP COLUMN IF EXISTS ai_model_id,
            DROP COLUMN IF EXISTS session_root,
            DROP COLUMN IF EXISTS repos,
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
    op.execute("DROP TABLE IF EXISTS sandbox_sync_queue CASCADE")
    op.execute("DROP TABLE IF EXISTS repositories       CASCADE")
    op.execute("DROP TABLE IF EXISTS ai_models          CASCADE")
    op.execute("DROP TABLE IF EXISTS ai_providers       CASCADE")
    op.execute("DROP TABLE IF EXISTS git_providers      CASCADE")
    op.execute("DROP TABLE IF EXISTS sandboxes          CASCADE")
