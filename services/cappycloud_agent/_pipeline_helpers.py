import json
import logging
import os
import uuid

import asyncpg
import httpx

from ._agent_context import inject_section_before_user_message
from ._agent_session import CLAUDE_CLI_MODEL_IDS
from ._workspace_paths import render_workspace_section, workspace_root_of

log = logging.getLogger(__name__)


def db_url() -> str:
    explicit = os.getenv("PIPELINE_DATABASE_URL", "").strip()
    raw = explicit or os.getenv("DATABASE_URL", "")
    return raw.replace("postgresql+asyncpg://", "postgresql://", 1)


def sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def inject_repo_context(user_message: str, repos: list, session_root: str) -> str:
    """Injeta comandos /add para cada worktree antes da mensagem do utilizador.

    Só para o openclaude, em sessões **multi-repo** (>1 repo): cada repo recebe
    um ``/add <path>`` para ele navegar entre os repositórios. O Claude CLI não
    tem esse comando e trataria as linhas como texto da pergunta.
    """
    if not repos or not session_root:
        return user_message
    # Workspace: a pasta da sessão já contém todos os repos; /add é desnecessário.
    if len(repos) <= 1 or workspace_root_of(session_root):
        return user_message

    add_lines: list[str] = []
    for repo in repos:
        alias = repo.get("alias") or repo.get("slug", "")
        if not alias:
            continue
        wt_path = repo.get("worktree_path") or f"{session_root}/{alias}"
        add_lines.append(f"/add {wt_path}")
        log.debug("Injecting /add %s", wt_path)

    if not add_lines:
        return user_message

    return "\n".join(add_lines) + "\n\n" + user_message


def add_workspace_section(prompt: str, repos: list[dict], session_root: str | None) -> str:
    """Seção ``## Workspace`` antes da mensagem do usuário (só em sessão de workspace).

    A estrutura dos worktrees entra depois, em ``validate_and_inject_worktree``,
    que já precisa listá-los para conferir que existem.
    """
    if not repos:
        return prompt
    section = render_workspace_section(session_root or "", repos)
    return inject_section_before_user_message(prompt, section) if section else prompt


async def push_mcp_config(
    database_url: str,
    sandbox_id: str,
    sandbox_session_url: str,
) -> None:
    """Busca MCPs ativos da sandbox no DB e envia ao sandbox via POST /mcp/configure.

    Degrada graciosamente: qualquer erro é logado como warning sem interromper o dispatch.
    """
    if not sandbox_id or not sandbox_session_url or not database_url:
        return
    try:
        sid = uuid.UUID(sandbox_id)
    except ValueError:
        return
    try:
        conn = await asyncpg.connect(database_url)
        try:
            rows = await conn.fetch(
                "SELECT name, command, args, env FROM mcp_servers "
                "WHERE sandbox_id = $1 AND enabled = true",
                sid,
            )
        finally:
            await conn.close()

        mcp_servers: dict = {}
        for row in rows:
            entry: dict = {"command": row["command"]}
            if row["args"]:
                args_val = row["args"]
                if isinstance(args_val, str):
                    args_val = json.loads(args_val)
                entry["args"] = list(args_val)
            if row["env"]:
                env_val = row["env"]
                if isinstance(env_val, str):
                    env_val = json.loads(env_val)
                entry["env"] = env_val if isinstance(env_val, dict) else dict(env_val)
            mcp_servers[row["name"]] = entry

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{sandbox_session_url}/mcp/configure",
                json={"mcpServers": mcp_servers},
            )
        log.info(
            "[MCP] config enviada ao sandbox: %d servidores → %s",
            len(mcp_servers),
            resp.status_code,
        )
    except Exception as exc:
        log.warning("[MCP] falha ao enviar config ao sandbox: %s", exc)


async def fetch_default_text_model_id(database_url: str) -> str | None:
    """Busca o modelo texto default ativo no catálogo do banco."""
    if not database_url:
        return None
    try:
        conn = await asyncpg.connect(database_url)
        try:
            row = await conn.fetchrow(
                """
                SELECT m.model_id
                FROM ai_models m
                JOIN ai_providers p ON p.id = m.provider_id
                WHERE m.active = TRUE
                  AND p.active = TRUE
                  AND COALESCE((m.is_default->>'text')::boolean, FALSE) = TRUE
                  AND m.capabilities ? 'text'
                ORDER BY m.display_name
                LIMIT 1
                """
            )
            if row:
                return str(row["model_id"])
            row = await conn.fetchrow(
                """
                SELECT m.model_id
                FROM ai_models m
                JOIN ai_providers p ON p.id = m.provider_id
                WHERE m.active = TRUE
                  AND p.active = TRUE
                  AND m.capabilities ? 'text'
                ORDER BY m.display_name
                LIMIT 1
                """
            )
            return str(row["model_id"]) if row else None
        finally:
            await conn.close()
    except Exception as exc:
        log.warning("[Models] falha ao buscar modelo default: %s", exc)
        return None


async def resolve_text_model_id(
    database_url: str, requested_model: str | None
) -> str | None:
    """Mantém o modelo pedido se ele estiver ativo e suportar texto."""
    if requested_model in CLAUDE_CLI_MODEL_IDS:
        return requested_model
    if database_url and requested_model:
        try:
            conn = await asyncpg.connect(database_url)
            try:
                row = await conn.fetchrow(
                    """
                    SELECT 1
                    FROM ai_models m
                    JOIN ai_providers p ON p.id = m.provider_id
                    WHERE m.active = TRUE
                      AND p.active = TRUE
                      AND m.model_id = $1
                      AND m.capabilities ? 'text'
                    LIMIT 1
                    """,
                    requested_model,
                )
                if row:
                    return requested_model
            finally:
                await conn.close()
        except Exception as exc:
            log.warning("[Models] falha ao validar modelo pedido: %s", exc)
    return await fetch_default_text_model_id(database_url)


resolve_free_text_model_id = resolve_text_model_id
