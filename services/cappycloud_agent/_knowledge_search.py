"""Consultas à memória (agentmemory) e ao grafo (graphify) do workspace.

Sem dependências além do httpx: roda na API (busca prévia do openclaude) e no
servidor MCP de evidências do sandbox (ferramenta do Claude CLI).
"""

from __future__ import annotations

import logging
import os

import httpx

log = logging.getLogger(__name__)

_MARKER = "## Mensagem do utilizador"
_QUERY_LIMIT = 300
MEMORY_LIMIT = int(os.getenv("KNOWLEDGE_PREFETCH_MEMORIES", "4"))
GRAPH_BUDGET = int(os.getenv("KNOWLEDGE_PREFETCH_GRAPH_BUDGET", "600"))


def question_text(user_message: str) -> str:
    """Só a pergunta (sem o contexto do pipeline), em uma linha, com limite."""
    text = user_message.split(_MARKER, 1)[1] if _MARKER in user_message else user_message
    return " ".join(text.split())[:_QUERY_LIMIT]


async def search_memory(
    client: httpx.AsyncClient, url: str, slug: str, question: str
) -> list[dict]:
    resp = await client.get(
        f"{url}/memory/search",
        params={"workspace": slug, "q": question, "limit": MEMORY_LIMIT},
    )
    if resp.status_code != 200:
        return []
    results = resp.json().get("results") or []
    return [item for item in results if str(item.get("content") or "").strip()]


async def query_graph(
    client: httpx.AsyncClient, url: str, slug: str, question: str, budget: int = GRAPH_BUDGET
) -> str:
    resp = await client.get(
        f"{url}/workspaces/{slug}/knowledge/query",
        params={"q": question, "budget": budget},
    )
    if resp.status_code != 200:
        return ""
    return str(resp.json().get("text") or "").strip()


async def safe(coro, empty):
    try:
        return await coro
    except Exception as exc:  # rede, JSON inválido, timeout: segue sem o achado
        log.info("[knowledge] consulta ignorada: %s", exc)
        return empty
