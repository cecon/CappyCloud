"""Claude CLI com sessão retomada: a mensagem vai sem o contexto recomposto.

O openclaude não guarda memória entre mensagens, então cada turno recebe o
contexto completo (workspace, estrutura dos repositórios, evidências). O
Claude Code retoma a sessão e já tem esse contexto no histórico: repeti-lo
custa ~10 s por mensagem e empilha dezenas de milhares de tokens por turno.
"""

from __future__ import annotations

import logging
import os

import httpx

log = logging.getLogger(__name__)


async def claude_cli_session_exists(session_url: str, conversation_key: str) -> bool:
    """True se o sandbox já tem sessão do Claude Code para esta conversa.

    Em qualquer erro devolve ``False``: na dúvida, o turno leva o contexto completo.
    """
    if not session_url or not conversation_key:
        return False
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"{session_url.rstrip('/')}/claude/sessions",
                params={"key": conversation_key},
                headers={"X-Internal-Token": os.getenv("INTERNAL_API_TOKEN", "").strip()},
            )
        return resp.status_code == 200 and resp.json().get("exists") is True
    except Exception as exc:
        log.warning("[ClaudeCLI] não consegui verificar a sessão %s: %s", conversation_key, exc)
        return False


async def claude_cli_agent_names(session_url: str) -> set[str]:
    """Subagentes gravados em ``~/.claude/agents`` do sandbox (vazio em erro).

    Os arquivos só existem depois do boot da sandbox pelo admin; até lá o
    prompt continua colando o perfil do arquiteto.
    """
    if not session_url:
        return set()
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"{session_url.rstrip('/')}/claude/agents",
                headers={"X-Internal-Token": os.getenv("INTERNAL_API_TOKEN", "").strip()},
            )
        if resp.status_code != 200:
            return set()
        return {str(name) for name in resp.json().get("names", [])}
    except Exception as exc:
        log.warning("[ClaudeCLI] não consegui listar os subagentes: %s", exc)
        return set()
