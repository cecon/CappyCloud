"""Memória e grafo do workspace consultados pela API a cada pergunta.

O agente só usava a memória (agentmemory) e o grafo (graphify) se lembrasse de
rodar os comandos descritos no CLAUDE.md, o que quase nunca acontecia: ele
partia direto para buscas no código, e cada busca reenvia o contexto inteiro.
Aqui a própria API faz as duas consultas com a pergunta do usuário e injeta só
os melhores achados, em texto curto, antes da mensagem.

Vale também para a sessão retomada do Claude CLI: o achado depende da pergunta,
então não está no histórico. Falha ou demora do sandbox nunca bloqueia o turno.
"""

from __future__ import annotations

import asyncio
import logging
import os

import httpx

from ._agent_context import inject_section_before_user_message
from ._workspace_paths import workspace_root_of

log = logging.getLogger(__name__)

_MARKER = "## Mensagem do utilizador"
_QUERY_LIMIT = 300
_MEMORY_LIMIT = int(os.getenv("KNOWLEDGE_PREFETCH_MEMORIES", "4"))
_MEMORY_CHARS = 500
_GRAPH_BUDGET = int(os.getenv("KNOWLEDGE_PREFETCH_GRAPH_BUDGET", "600"))
_GRAPH_CHARS = 2500
_TIMEOUT_S = 8.0


def question_text(user_message: str) -> str:
    """Só a pergunta (sem o contexto do pipeline), em uma linha, com limite."""
    text = user_message.split(_MARKER, 1)[1] if _MARKER in user_message else user_message
    return " ".join(text.split())[:_QUERY_LIMIT]


async def _search_memory(
    client: httpx.AsyncClient, url: str, slug: str, question: str
) -> list[dict]:
    resp = await client.get(
        f"{url}/memory/search",
        params={"workspace": slug, "q": question, "limit": _MEMORY_LIMIT},
    )
    if resp.status_code != 200:
        return []
    results = resp.json().get("results") or []
    return [item for item in results if str(item.get("content") or "").strip()]


async def _query_graph(client: httpx.AsyncClient, url: str, slug: str, question: str) -> str:
    resp = await client.get(
        f"{url}/workspaces/{slug}/knowledge/query",
        params={"q": question, "budget": _GRAPH_BUDGET},
    )
    if resp.status_code != 200:
        return ""
    return str(resp.json().get("text") or "").strip()


async def _safe(coro, empty):
    try:
        return await coro
    except Exception as exc:  # rede, JSON inválido, timeout: segue sem o achado
        log.info("[knowledge_prefetch] consulta ignorada: %s", exc)
        return empty


def render_knowledge_section(memories: list[dict], graph: str) -> str:
    """Seção curta com o que já se sabe; vazia quando nada foi achado."""
    if not memories and not graph:
        return ""
    lines = [
        "## Conhecimento do workspace (consultado automaticamente para esta pergunta)",
        "Comece por aqui. Confira no código só o que for preciso para responder;",
        "se isto já responde, não refaça a investigação.",
    ]
    if memories:
        lines += ["", "### Memória (o que conversas anteriores confirmaram)"]
        for item in memories[:_MEMORY_LIMIT]:
            content = " ".join(str(item.get("content")).split())[:_MEMORY_CHARS]
            files = ", ".join(str(f) for f in (item.get("files") or [])[:3])
            suffix = f" (arquivos: {files})" if files else ""
            lines.append(f"- [{item.get('type') or 'fact'}] {content}{suffix}")
    if graph:
        lines += ["", "### Grafo de código (graphify, branch principal)", graph[:_GRAPH_CHARS]]
    return "\n".join(lines)


async def inject_workspace_knowledge(
    prompt: str,
    *,
    user_message: str,
    sandbox_session_url: str,
    session_root: str,
) -> str:
    """Injeta memória e grafo relevantes antes da mensagem do usuário."""
    root = workspace_root_of(session_root)
    question = question_text(user_message or "")
    if not root or not sandbox_session_url or not question:
        return prompt
    slug = root.rsplit("/", 1)[-1]
    url = sandbox_session_url.rstrip("/")
    async with httpx.AsyncClient(timeout=httpx.Timeout(_TIMEOUT_S)) as client:
        memories, graph = await asyncio.gather(
            _safe(_search_memory(client, url, slug, question), []),
            _safe(_query_graph(client, url, slug, question), ""),
        )
    section = render_knowledge_section(memories, graph)
    return inject_section_before_user_message(prompt, section) if section else prompt
