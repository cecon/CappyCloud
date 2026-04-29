"""Helpers para enriquecer o prompt do utilizador com contexto técnico.

Carrega um conjunto inicial de Skills relevantes via busca lexical no Postgres.
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
_SKILL_CONTENT_MAX_CHARS = int(os.getenv("SKILL_CONTENT_MAX_CHARS", "1200"))


def _trim_skill_content(content: str | None) -> str:
    """Limita conteúdo de skill injetado no prompt inicial."""
    if not content:
        return ""
    text = content.strip()
    if len(text) <= _SKILL_CONTENT_MAX_CHARS:
        return text
    return text[:_SKILL_CONTENT_MAX_CHARS].rstrip() + "\n..."


async def _load_repo_skills(
    conn: asyncpg.Connection,
    repo_ids: list[str],
    user_message: str,
    top_n: int,
) -> list[dict]:
    """Carrega skills vinculadas a repositórios específicos da sessão."""
    if not repo_ids:
        return []

    keywords = [w for w in user_message.split() if len(w) > 4][:6]
    pattern = f"%{keywords[0]}%" if keywords else "%"

    placeholders = ", ".join(f"${i + 3}::uuid" for i in range(len(repo_ids)))
    rows = await conn.fetch(
        f"SELECT title, summary, content, source_url FROM skills "
        f"WHERE active = TRUE AND repository_id IN ({placeholders}) "
        f"AND (title ILIKE $1 OR summary ILIKE $1 OR content ILIKE $1) "
        f"ORDER BY title LIMIT $2",
        pattern,
        top_n,
        *repo_ids,
    )
    return [
        {
            "title": r["title"],
            "summary": r["summary"] or "",
            "content": _trim_skill_content(r["content"]),
            "source_url": r["source_url"],
        }
        for r in rows
    ]


async def load_agent_context(
    db_url: str,
    user_message: str,
    repo_ids: list[str] | None = None,
) -> list[dict]:
    """Devolve skills relevantes para os repositórios da sessão."""
    if not db_url:
        return []

    conn: Optional[asyncpg.Connection] = None
    try:
        conn = await asyncpg.connect(db_url)

        skills: list[dict] = []

        # Skills vinculadas ao(s) repositório(s) da sessão.
        if repo_ids:
            repo_skills = await _load_repo_skills(
                conn, repo_ids, user_message, _RAG_TOP_N
            )
            existing_titles = {s["title"] for s in skills}
            for rs in repo_skills:
                if rs["title"] not in existing_titles:
                    skills.append(rs)
                    existing_titles.add(rs["title"])
        return skills
    except Exception as exc:  # noqa: BLE001 - degrada graciosamente
        log.warning("load_agent_context falhou: %s", exc)
        return []
    finally:
        if conn:
            await conn.close()


def build_prompt_with_agent(
    user_message: str,
    skills: list[dict],
    sandbox_session_url: str,
    repos: list[dict] | None = None,
    session_root: str = "",
) -> str:
    """Monta o prompt final colando top-N skills + msg do user.

    Inclui também o **caminho absoluto do worktree** quando há repos
    associados — necessário porque o openclaude por vezes executa tools
    no CWD do servidor (``/openclaude``) em vez do worktree, e usar
    paths absolutos resolve esse bug. Também instrui a chamar
    ``GET <sandbox>/skills/search?q=...`` via Bash para RAG por demanda.
    """
    parts: list[str] = []

    # Worktree paths absolutos — força o agente a usá-los em todos os comandos
    # (rg, find, ls, cat) para evitar o bug de CWD do openclaude.
    worktree_paths: list[str] = []
    for r in repos or []:
        wt = r.get("worktree_path")
        if not wt and session_root:
            alias = r.get("alias") or r.get("slug", "")
            if alias:
                wt = f"{session_root.rstrip('/')}/{alias}"
        if wt:
            worktree_paths.append(wt)

    if worktree_paths:
        # Conciso: bloco curto evita que LLMs pequenos leiam isto e respondam
        # baseados no plano em vez de invocar tools reais.
        wt_str = "\n".join(f"- `{p}`" for p in worktree_paths)
        parts.append(
            "## Worktree\n\n"
            "Use sempre estes caminhos absolutos em Bash/Grep/Read "
            "(não confies em `pwd`):\n" + wt_str
        )

    if skills:
        kb_lines = ["## Conhecimento disponível (top resultados)"]
        for s in skills:
            line = f"- **{s['title']}**"
            if s.get("summary"):
                line += f" — {s['summary']}"
            if s.get("source_url"):
                line += f"  \n  Fonte: {s['source_url']}"
            kb_lines.append(line)
            if s.get("content"):
                kb_lines.append(f"\n{s['content']}")
        parts.append("\n".join(kb_lines))

    if sandbox_session_url:
        parts.append(
            "## Ferramentas do servidor de sessão\n\n"
            "### Busca de documentação\n"
            "Para consultar mais documentação relevante, executa via Bash:\n"
            f"`curl -s '{sandbox_session_url}/skills/search?q=<termo>'`\n"
            "(retorna JSON com slug/title/summary/content das skills mais próximas).\n\n"
            "### Sub-agente de investigação\n"
            "Para delegar uma investigação a um sub-agente especializado, executa via Bash:\n"
            "```bash\n"
            f"curl -s -X POST '{sandbox_session_url}/task' \\\n"
            "  -H 'Content-Type: application/json' \\\n"
            "  -d '{\"description\":\"<título>\",\"prompt\":\"<instrução completa>\"}'\n"
            "```\n"
            "O campo `result` da resposta contém o texto produzido pelo sub-agente.\n"
            "Use `jq -r '.result'` para extrair apenas o texto."
        )

    parts.append("## Mensagem do utilizador\n\n" + user_message)

    return "\n\n---\n\n".join(parts)
