"""Helpers para enriquecer o prompt do utilizador com contexto do Agente.

Carrega o ``system_prompt`` do agente associado à conversa e (opcionalmente)
um conjunto inicial de Skills relevantes via busca lexical no Postgres.
A busca semântica completa fica disponível ao LLM por demanda em
``GET /skills/search`` no session_server do sandbox.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import asyncpg

log = logging.getLogger(__name__)

_RAG_TOP_N = int(os.getenv("RAG_TOP_N", "3"))


async def load_agent_context(
    db_url: str, agent_id: str, user_message: str
) -> tuple[str, list[dict]]:
    """Devolve ``(system_prompt, [{title, summary, source_url}, ...])``."""
    if not agent_id or not db_url:
        return "", []

    conn: Optional[asyncpg.Connection] = None
    try:
        conn = await asyncpg.connect(db_url)
        agent_row = await conn.fetchrow(
            "SELECT system_prompt FROM agents WHERE id = $1::uuid AND active = TRUE",
            agent_id,
        )
        if not agent_row:
            return "", []

        system_prompt = agent_row["system_prompt"] or ""

        # Match lexical simples: a primeira palavra-chave longa da mensagem.
        keywords = [w for w in user_message.split() if len(w) > 4][:6]
        skills: list[dict] = []
        if keywords:
            pattern = f"%{keywords[0]}%"
            rows = await conn.fetch(
                "SELECT title, summary, source_url FROM skills "
                "WHERE active = TRUE AND (agent_id = $1::uuid OR agent_id IS NULL) "
                "AND (title ILIKE $2 OR summary ILIKE $2 OR content ILIKE $2) "
                "ORDER BY title LIMIT $3",
                agent_id,
                pattern,
                _RAG_TOP_N,
            )
            for r in rows:
                skills.append(
                    {
                        "title": r["title"],
                        "summary": r["summary"] or "",
                        "source_url": r["source_url"],
                    }
                )
        return system_prompt, skills
    except Exception as exc:  # noqa: BLE001 - degrada graciosamente
        log.warning("load_agent_context falhou (agent=%s): %s", agent_id[:8], exc)
        return "", []
    finally:
        if conn:
            await conn.close()


def build_prompt_with_agent(
    user_message: str,
    system_prompt: str,
    skills: list[dict],
    sandbox_session_url: str,
) -> str:
    """Monta o prompt final colando system_prompt + top-N skills + msg do user.

    Sempre inclui instrução para chamar ``GET <sandbox>/skills/search?q=...``
    via Bash quando o LLM precisar de mais contexto (RAG por demanda).
    """
    parts: list[str] = []

    if system_prompt.strip():
        parts.append("## Instruções do agente\n\n" + system_prompt.strip())

    if skills:
        kb_lines = ["## Conhecimento disponível (top resultados)"]
        for s in skills:
            line = f"- **{s['title']}**"
            if s.get("summary"):
                line += f" — {s['summary']}"
            if s.get("source_url"):
                line += f"  \n  Fonte: {s['source_url']}"
            kb_lines.append(line)
        parts.append("\n".join(kb_lines))

    if sandbox_session_url:
        parts.append(
            "## Como aprofundar\n\n"
            "Para consultar mais documentação relevante, executa via Bash:\n"
            f"`curl -s '{sandbox_session_url}/skills/search?q=<termo>'`\n"
            "(retorna JSON com slug/title/summary/content das skills mais próximas)."
        )

    parts.append("## Mensagem do utilizador\n\n" + user_message)

    return "\n\n---\n\n".join(parts)
