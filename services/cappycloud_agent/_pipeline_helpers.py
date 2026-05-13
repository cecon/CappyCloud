import json
import logging
import os
import uuid

import asyncpg
import httpx

from ._agent_context import (
    fetch_worktree_top_levels,
    inject_section_before_user_message,
    render_worktree_top_level_section,
)

log = logging.getLogger(__name__)


def db_url() -> str:
    explicit = os.getenv("PIPELINE_DATABASE_URL", "").strip()
    if explicit:
        return explicit
    return os.getenv("DATABASE_URL", "").replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )


def sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def inject_repo_context(user_message: str, repos: list, session_root: str) -> str:
    """Injeta comandos /add para cada worktree antes da mensagem do utilizador.

    Apenas relevante em sessões **multi-repo** (>1 repo): cada repo recebe um
    ``/add <path>`` para o openclaude conseguir navegar entre os repositórios.
    """
    if not repos or not session_root:
        return user_message
    if len(repos) <= 1:
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


async def build_prompt_with_worktree_context(
    prompt: str,
    sandbox_session_url: str,
    repos: list[dict],
    session_root: str | None,
) -> str:
    """Injeta snapshot do worktree no prompt. Degrada graciosamente em caso de erro."""
    if not repos:
        return prompt
    try:
        top_level = await fetch_worktree_top_levels(sandbox_session_url, repos, session_root)
        section = render_worktree_top_level_section(top_level)
        if section:
            return inject_section_before_user_message(prompt, section)
    except Exception as exc:  # noqa: BLE001
        log.warning("[Dispatcher] worktree top-level fetch falhou: %s", exc)
    return prompt


async def push_mcp_config(
    database_url: str,
    user_id: str,
    sandbox_session_url: str,
) -> None:
    """Busca MCPs ativos do utilizador no DB e envia ao sandbox via POST /mcp/configure.

    Degrada graciosamente: qualquer erro é logado como warning sem interromper o dispatch.
    """
    if not user_id or not sandbox_session_url or not database_url:
        return
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        return
    try:
        conn = await asyncpg.connect(database_url)
        try:
            rows = await conn.fetch(
                "SELECT name, command, args, env FROM mcp_servers "
                "WHERE user_id = $1 AND enabled = true",
                uid,
            )
        finally:
            await conn.close()

        mcp_servers: dict = {}
        for row in rows:
            entry: dict = {"command": row["command"]}
            if row["args"]:
                entry["args"] = list(row["args"])
            if row["env"]:
                entry["env"] = dict(row["env"])
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
    except Exception as exc:  # noqa: BLE001
        log.warning("[MCP] falha ao enviar config ao sandbox: %s", exc)
