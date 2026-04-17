-- ──────────────────────────────────────────────────────────────
-- Migration 02 — Platform Control Plane
--
-- Tudo que estava no .env agora vive no banco:
--   git_providers  — tokens de GitHub/Azure DevOps/GitLab (criptografados)
--   ai_providers   — chaves de API de provedores LLM
--   ai_models      — catálogo de modelos com capabilities
--   repositories   — repos git com estado de sync no sandbox
--   sandbox_sync_queue — fila do cão de guarda (DB → sandbox VM)
--
-- Conversas ganham rastreamento de PR, CI e diff stats.
-- ──────────────────────────────────────────────────────────────

-- ── Provedores de repositórios git ───────────────────────────
-- type: github | azure_devops | gitlab | bitbucket
-- token_encrypted: PAT criptografado com Fernet (ENCRYPTION_KEY)
CREATE TABLE IF NOT EXISTS git_providers (
    id               UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    name             VARCHAR(128) NOT NULL,
    provider_type    VARCHAR(32)  NOT NULL DEFAULT 'github',
    base_url         TEXT         NOT NULL DEFAULT '',
    org_or_project   TEXT         NOT NULL DEFAULT '',
    token_encrypted  TEXT         NOT NULL DEFAULT '',
    active           BOOLEAN      NOT NULL DEFAULT true,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_git_providers_type ON git_providers(provider_type);

-- ── Provedores de IA (OpenRouter, Anthropic, OpenAI…) ────────
CREATE TABLE IF NOT EXISTS ai_providers (
    id               UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    name             VARCHAR(128) UNIQUE NOT NULL,
    base_url         TEXT         NOT NULL DEFAULT 'https://openrouter.ai/api/v1',
    api_key_encrypted TEXT        NOT NULL DEFAULT '',
    active           BOOLEAN      NOT NULL DEFAULT true,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Seed do provider padrão (OpenRouter) — token preenchido via UI
INSERT INTO ai_providers (name, base_url)
VALUES ('openrouter', 'https://openrouter.ai/api/v1')
ON CONFLICT (name) DO NOTHING;

-- ── Catálogo de modelos de IA ─────────────────────────────────
-- capabilities: array JSON de strings ['text','vision','embedding','video']
-- is_default JSONB: {"text": true, "vision": false, ...}
CREATE TABLE IF NOT EXISTS ai_models (
    id              UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    provider_id     UUID         REFERENCES ai_providers(id) ON DELETE CASCADE,
    model_id        VARCHAR(256) NOT NULL,
    display_name    VARCHAR(256) NOT NULL,
    capabilities    JSONB        NOT NULL DEFAULT '["text"]',
    is_default      JSONB        NOT NULL DEFAULT '{}',
    context_window  INTEGER      NOT NULL DEFAULT 200000,
    active          BOOLEAN      NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (provider_id, model_id)
);

CREATE INDEX IF NOT EXISTS ix_ai_models_provider ON ai_models(provider_id);
CREATE INDEX IF NOT EXISTS ix_ai_models_active   ON ai_models(active);

-- Modelos padrão (OpenRouter)
INSERT INTO ai_models (provider_id, model_id, display_name, capabilities, is_default, context_window)
SELECT p.id, m.model_id, m.display_name, m.capabilities::jsonb, m.is_default::jsonb, m.ctx
FROM ai_providers p
CROSS JOIN (VALUES
    ('anthropic/claude-3.5-sonnet', 'Claude 3.5 Sonnet',   '["text","vision"]',        '{"text":true}',      200000),
    ('anthropic/claude-3-haiku',    'Claude 3 Haiku',       '["text","vision"]',        '{}',                 200000),
    ('openai/gpt-4o',               'GPT-4o',               '["text","vision"]',        '{"vision":true}',   128000),
    ('openai/gpt-4o-mini',          'GPT-4o mini',          '["text"]',                 '{}',                128000),
    ('openai/text-embedding-3-large','Embedding 3 Large',   '["embedding"]',            '{"embedding":true}',8192),
    ('openai/gpt-4.1',              'GPT-4.1',              '["text","vision"]',        '{}',               1047576)
) AS m(model_id, display_name, capabilities, is_default, ctx)
WHERE p.name = 'openrouter'
ON CONFLICT (provider_id, model_id) DO NOTHING;

-- ── Repositórios git com estado de sync ───────────────────────
-- sandbox_status: not_cloned | cloning | cloned | error
CREATE TABLE IF NOT EXISTS repositories (
    id              UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug            VARCHAR(128) UNIQUE NOT NULL,
    name            VARCHAR(256) NOT NULL,
    provider_id     UUID         REFERENCES git_providers(id) ON DELETE SET NULL,
    clone_url       TEXT         NOT NULL,
    default_branch  VARCHAR(256) NOT NULL DEFAULT 'main',
    sandbox_id      UUID         REFERENCES sandboxes(id) ON DELETE SET NULL,
    sandbox_status  VARCHAR(32)  NOT NULL DEFAULT 'not_cloned',
    sandbox_path    TEXT         NOT NULL DEFAULT '',
    last_sync_at    TIMESTAMPTZ,
    error_message   TEXT,
    active          BOOLEAN      NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_repositories_sandbox    ON repositories(sandbox_id);
CREATE INDEX IF NOT EXISTS ix_repositories_sandbox_st ON repositories(sandbox_status);

-- ── Fila de sincronização (cão de guarda DB → sandbox) ───────
-- operation: clone_repo | remove_repo | update_git_auth | reconfigure_model
-- status: pending | processing | done | error
CREATE TABLE IF NOT EXISTS sandbox_sync_queue (
    id           UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    sandbox_id   UUID         NOT NULL REFERENCES sandboxes(id) ON DELETE CASCADE,
    operation    VARCHAR(64)  NOT NULL,
    payload      JSONB        NOT NULL DEFAULT '{}',
    priority     INTEGER      NOT NULL DEFAULT 5,
    status       VARCHAR(32)  NOT NULL DEFAULT 'pending',
    retries      INTEGER      NOT NULL DEFAULT 0,
    last_error   TEXT,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_sync_queue_status   ON sandbox_sync_queue(status, priority, created_at);
CREATE INDEX IF NOT EXISTS ix_sync_queue_sandbox  ON sandbox_sync_queue(sandbox_id);

-- ── Conversations: rastreamento de PR, CI e diff ─────────────
ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS ai_model_id    UUID    REFERENCES ai_models(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS worktree_exists BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS lines_added    INTEGER  NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS lines_removed  INTEGER  NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS files_changed  INTEGER  NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS pr_url         TEXT,
    ADD COLUMN IF NOT EXISTS pr_status      VARCHAR(32) NOT NULL DEFAULT 'none',
    ADD COLUMN IF NOT EXISTS pr_approved    BOOLEAN  NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS ci_status      VARCHAR(32) NOT NULL DEFAULT 'unknown',
    ADD COLUMN IF NOT EXISTS ci_url         TEXT;

CREATE INDEX IF NOT EXISTS ix_conversations_ai_model ON conversations(ai_model_id);
