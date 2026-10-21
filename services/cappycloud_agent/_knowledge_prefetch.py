"""Memória e grafo do workspace consultados pela API a cada pergunta.

O agente só usava a memória (agentmemory) e o grafo (graphify) se lembrasse de
rodar os comandos descritos no CLAUDE.md, o que quase nunca acontecia: ele
partia direto para buscas no código, e cada busca reenvia o contexto inteiro.
Aqui a própria API faz as duas consultas com a pergunta do usuário e injeta só
os melhores achados, em texto curto, antes da mensagem.

Hoje só o openclaude recebe esta seção. O Claude CLI consulta o mesmo conteúdo
sob demanda pela ferramenta ``consultar_conhecimento_workspace`` (_evidence_tool).
Falha ou demora do sandbox nunca bloqueia o turno.
"""

from __future__ import annotations

import asyncio

import httpx

from ._agent_context import inject_section_before_user_message
from ._knowledge_search import MEMORY_LIMIT, query_graph, question_text, safe, search_memory
from ._workspace_paths import workspace_root_of

__all__ = ["inject_workspace_knowledge", "question_text", "render_knowledge_section"]

_MEMORY_CHARS = 500
_GRAPH_CHARS = 2500
_TIMEOUT_S = 8.0


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
        for item in memories[:MEMORY_LIMIT]:
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
            safe(search_memory(client, url, slug, question), []),
            safe(query_graph(client, url, slug, question), ""),
        )
    section = render_knowledge_section(memories, graph)
    return inject_section_before_user_message(prompt, section) if section else prompt
