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
import httpx

log = logging.getLogger(__name__)

_RAG_TOP_N = int(os.getenv("RAG_TOP_N", "3"))
_SKILL_CONTENT_MAX_CHARS = int(os.getenv("SKILL_CONTENT_MAX_CHARS", "1200"))
_TOPLEVEL_LIMIT = int(os.getenv("WORKTREE_TOPLEVEL_LIMIT", "20"))


async def fetch_worktree_top_levels(
    session_url: str,
    repos: list[dict] | None,
    session_root: str = "",
    limit: int = _TOPLEVEL_LIMIT,
) -> dict[str, list[str]]:
    """Faz fetch da estrutura top-level para todos os worktrees configurados.

    Deve ser chamada **depois** de o worktree existir (após
    ``EnvironmentManager.get_or_create_session``); caso contrário
    ``/worktree/ls-files`` devolve 500 e o resultado fica vazio.
    """
    if not session_url or not repos:
        return {}
    out: dict[str, list[str]] = {}
    for repo in repos:
        wt = repo.get("worktree_path")
        if not wt and session_root:
            alias = repo.get("alias") or repo.get("slug", "")
            if alias:
                wt = f"{session_root.rstrip('/')}/{alias}"
        if not wt:
            continue
        entries = await _fetch_worktree_top_level(session_url, wt, limit=limit)
        if entries:
            out[wt] = entries
    return out


def render_worktree_top_level_section(
    worktree_top_level: dict[str, list[str]],
) -> str:
    """Renderiza o bloco markdown com a estrutura top-level dos worktrees."""
    if not worktree_top_level:
        return ""
    sections: list[str] = []
    for path, entries in worktree_top_level.items():
        if not entries:
            continue
        listing = "\n".join(f"- {e}" for e in entries)
        sections.append(f"### `{path}`\n{listing}")
    if not sections:
        return ""
    return (
        "## Estrutura do worktree (top-level)\n\n"
        "Confirma com `ls`/`git ls-files` antes de afirmar que "
        "alguma pasta não existe:\n\n" + "\n\n".join(sections)
    )


def inject_section_before_user_message(prompt: str, section: str) -> str:
    """Insere ``section`` antes de ``## Mensagem do utilizador`` (ou append)."""
    if not section:
        return prompt
    marker = "## Mensagem do utilizador"
    idx = prompt.rfind(marker)
    sep = "\n\n---\n\n"
    if idx == -1:
        return prompt + sep + section
    sep_idx = prompt.rfind(sep, 0, idx)
    if sep_idx == -1:
        return section + sep + prompt
    return prompt[:sep_idx] + sep + section + prompt[sep_idx:]


async def _fetch_worktree_top_level(
    session_url: str, worktree_path: str, limit: int = _TOPLEVEL_LIMIT
) -> list[str]:
    """Lista entradas top-level do worktree via ``/worktree/ls-files``.

    Dá ao modelo um snapshot inicial barato em vez de o forçar a descobrir
    a estrutura com sucessivos ``ls``/``Glob``.
    """
    if not session_url or not worktree_path:
        return []
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                f"{session_url.rstrip('/')}/worktree/ls-files",
                json={"worktree_path": worktree_path},
            )
        if resp.status_code != 200:
            return []
        files = resp.json().get("files") or []
    except Exception as exc:  # noqa: BLE001 - degrada graciosamente
        log.debug("ls-files falhou para %s: %s", worktree_path, exc)
        return []

    top: dict[str, bool] = {}
    for f in files:
        if not f:
            continue
        head = f.split("/", 1)[0]
        is_dir = "/" in f
        if head not in top or is_dir:
            top[head] = is_dir
    out = sorted(top.items(), key=lambda kv: (not kv[1], kv[0].lower()))
    return [f"{name}/" if is_dir else name for name, is_dir in out[:limit]]


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
    worktree_top_level: dict[str, list[str]] | None = None,
) -> str:
    """Monta o prompt final colando top-N skills + msg do user.

    Inclui também o **caminho absoluto do worktree** quando há repos
    associados — necessário porque o openclaude por vezes executa tools
    no CWD do servidor (``/openclaude``) em vez do worktree, e usar
    paths absolutos resolve esse bug. Também instrui a chamar
    ``GET <sandbox>/skills/search?q=...`` via Bash para RAG por demanda.

    ``worktree_top_level`` (opcional) mapeia ``worktree_path`` → lista de
    entradas top-level do repo (pastas/ficheiros). Quando presente, é
    incluído no prompt para dar fundação a modelos pequenos.
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

        # Estrutura top-level do(s) worktree(s) — fundação para modelos pequenos
        # decidirem onde procurar antes de qualquer grep/glob.
        if worktree_top_level:
            sections: list[str] = []
            for path in worktree_paths:
                entries = worktree_top_level.get(path) or []
                if not entries:
                    continue
                listing = "\n".join(f"- {e}" for e in entries)
                sections.append(f"### `{path}`\n{listing}")
            if sections:
                parts.append(
                    "## Estrutura do worktree (top-level)\n\n"
                    "Confirma com `ls`/`git ls-files` antes de afirmar que "
                    "alguma pasta não existe:\n\n" + "\n\n".join(sections)
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
