"""Runtime do agente configurado na sandbox (openclaude ou Claude CLI)."""

from __future__ import annotations

import logging

import asyncpg

from ._agent_session import AGENT_RUNTIME_OPENCLAUDE

log = logging.getLogger(__name__)


async def resolve_agent_runtime(database_url: str, sandbox_id: str) -> str:
    """Lido a cada turno, não fica no ``SandboxRecord`` da sessão: trocar o
    runtime no admin vale já na próxima mensagem, inclusive em conversas abertas.
    """
    if not sandbox_id or not database_url:
        return AGENT_RUNTIME_OPENCLAUDE
    try:
        conn = await asyncpg.connect(database_url)
        try:
            value = await conn.fetchval(
                "SELECT agent_runtime FROM sandboxes WHERE id = $1::uuid", sandbox_id
            )
        finally:
            await conn.close()
    except Exception as exc:
        log.warning("Falha ao ler agent_runtime da sandbox %s: %s", sandbox_id, exc)
        return AGENT_RUNTIME_OPENCLAUDE
    return str(value or AGENT_RUNTIME_OPENCLAUDE)
