-- ──────────────────────────────────────────────────────────────
-- Migration 01 — Sandboxes escaláveis + sessões multi-repo
--
-- Roda uma única vez no init do volume PostgreSQL (após 00-extensions.sql).
-- Caso o banco já exista, todas as operações são idempotentes (IF NOT EXISTS,
-- ADD COLUMN IF NOT EXISTS, ON CONFLICT DO NOTHING).
--
-- Novo modelo:
--   sandboxes   — registry de instâncias do container sandbox
--   conversations — ganha repos JSONB (multi-repo), session_root, sandbox_id
--   agent_tasks — ganha sandbox_id
-- ──────────────────────────────────────────────────────────────

-- ── Sandboxes ─────────────────────────────────────────────────
-- Cada linha representa um container sandbox rodando openclaude gRPC.
-- status: active | draining (sem novas sessões) | offline
CREATE TABLE IF NOT EXISTS sandboxes (
    id           UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    name         VARCHAR(128) UNIQUE NOT NULL,
    host         VARCHAR(256) NOT NULL,
    grpc_port    INTEGER      NOT NULL DEFAULT 50051,
    session_port INTEGER      NOT NULL DEFAULT 8080,
    status       VARCHAR(32)  NOT NULL DEFAULT 'active',
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Sandbox padrão configurado pelo docker-compose
INSERT INTO sandboxes (name, host, grpc_port, session_port, status)
VALUES ('cappycloud-sandbox', 'cappycloud-sandbox', 50051, 8080, 'active')
ON CONFLICT (name) DO NOTHING;

-- ── conversations: suporte a multi-repo ───────────────────────
-- repos: lista ordenada de {slug, alias, base_branch, branch_name, worktree_path}
-- session_root: diretório raiz da sessão no volume, ex.: /repos/sessions/<short_id>/
-- sandbox_id: qual sandbox hospeda esta sessão (FK soft — sem FK hard para evitar
--             bloqueio se sandbox for deletado)
ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS repos        JSONB   NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS session_root TEXT,
    ADD COLUMN IF NOT EXISTS sandbox_id   UUID    REFERENCES sandboxes(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_conversations_sandbox_id ON conversations(sandbox_id);

-- ── agent_tasks: referência ao sandbox ───────────────────────
ALTER TABLE agent_tasks
    ADD COLUMN IF NOT EXISTS sandbox_id UUID REFERENCES sandboxes(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_agent_tasks_sandbox_id ON agent_tasks(sandbox_id);
