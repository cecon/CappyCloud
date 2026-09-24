"""Helpers para enriquecer o prompt do utilizador com contexto técnico.

Carrega um conjunto inicial de Skills relevantes via busca lexical no Postgres.
A busca semântica completa fica disponível ao LLM por demanda em
``GET /skills/search`` no session_server do sandbox.
"""

from __future__ import annotations

import logging
import os
import re
import uuid

import asyncpg
import httpx

log = logging.getLogger(__name__)

from ._agent_prompt_sections import (  # noqa: E402
    render_execution_profile,
    render_repo_agents,
    render_repo_skills,
    render_session_tools,
)

_RAG_TOP_N = int(os.getenv("RAG_TOP_N", "3"))
_REPO_SKILLS_LIMIT = int(os.getenv("REPO_SKILLS_LIMIT", "20"))
_TOPLEVEL_LIMIT = int(os.getenv("WORKTREE_TOPLEVEL_LIMIT", "80"))


def _asyncpg_dsn(db_url: str) -> str:
    """Converte DSN SQLAlchemy async em DSN aceita por asyncpg."""
    return (db_url or "").replace("postgresql+asyncpg://", "postgresql://", 1)


async def fetch_worktree_top_levels(
    session_url: str,
    repos: list[dict] | None,
    session_root: str = "",
    limit: int = _TOPLEVEL_LIMIT,
) -> dict[str, list[str]]:
    """Busca uma amostra top-level dos worktrees já criados no sandbox."""
    if not session_url or not repos:
        return {}
    out: dict[str, list[str]] = {}
    for repo in repos:
        worktree_path = repo.get("worktree_path")
        if not worktree_path and session_root:
            alias = repo.get("alias") or repo.get("slug", "")
            if alias:
                worktree_path = f"{session_root.rstrip('/')}/{alias}"
        if not worktree_path:
            continue
        entries = await _fetch_worktree_top_level(session_url, worktree_path, limit)
        if entries:
            out[worktree_path] = entries
    return out


def render_worktree_top_level_section(
    worktree_top_level: dict[str, list[str]],
) -> str:
    """Renderiza o snapshot top-level para injetar antes da mensagem do usuário."""
    if not worktree_top_level:
        return ""
    sections: list[str] = []
    for path, entries in worktree_top_level.items():
        if entries:
            body = "\n".join(f"- {entry}" for entry in entries)
            sections.append(f"`{path}`:\n{body}")
    if not sections:
        return ""
    return (
        "## Estrutura do worktree\n\n"
        "O repositório já foi provisionado. Use estes caminhos absolutos ao "
        "consultar arquivos e nunca conclua que a pasta está vazia sem rodar "
        "`ls` ou `git ls-files` no worktree:\n\n" + "\n\n".join(sections)
    )


def inject_section_before_user_message(prompt: str, section: str) -> str:
    """Insere um bloco de contexto imediatamente antes da mensagem do usuário."""
    if not section.strip():
        return prompt
    marker = "## Mensagem do utilizador"
    if marker not in prompt:
        return f"{section.strip()}\n\n---\n\n{prompt}"
    return prompt.replace(marker, f"{section.strip()}\n\n---\n\n{marker}", 1)


async def _fetch_worktree_top_level(
    session_url: str,
    worktree_path: str,
    limit: int,
) -> list[str]:
    """Lista entradas top-level tracked via endpoint HTTP do sandbox."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"{session_url.rstrip('/')}/git/ls-files",
                params={"worktree_path": worktree_path},
            )
        if resp.status_code != 200:
            return []
        files = resp.json().get("files") or []
    except Exception as exc:
        log.debug("ls-files falhou para %s: %s", worktree_path, exc)
        return []

    top_level: list[str] = []
    seen: set[str] = set()
    for raw in files:
        name = str(raw).split("/", 1)[0].strip()
        if not name or name in seen:
            continue
        seen.add(name)
        top_level.append(name)
        if len(top_level) >= limit:
            break
    return top_level


async def _load_repo_skills(
    conn: asyncpg.Connection,
    repo_ids: list[str],
    user_message: str,
    top_n: int,
) -> list[dict]:
    """Carrega skills vinculadas a repositórios específicos da sessão."""
    if not repo_ids:
        return []

    placeholders = ", ".join(f"${i + 2}::uuid" for i in range(len(repo_ids)))
    rows = await conn.fetch(
        f"SELECT title, summary, source_url FROM skills "
        f"WHERE active = TRUE AND repository_id IN ({placeholders}) "
        f"AND document_id IS NULL "
        f"ORDER BY title LIMIT $1",
        top_n,
        *repo_ids,
    )
    return [
        {
            "title": r["title"],
            "summary": r["summary"] or "",
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

    conn: asyncpg.Connection | None = None
    try:
        conn = await asyncpg.connect(_asyncpg_dsn(db_url))

        skills: list[dict] = []

        # Skills vinculadas ao(s) repositório(s) da sessão.
        if repo_ids:
            repo_skills = await _load_repo_skills(
                conn, repo_ids, user_message, _REPO_SKILLS_LIMIT
            )
            existing_titles = {s["title"] for s in skills}
            for rs in repo_skills:
                if rs["title"] not in existing_titles:
                    skills.append(rs)
                    existing_titles.add(rs["title"])
        return skills
    except Exception as exc:
        log.warning("load_agent_context falhou: %s", exc)
        return []
    finally:
        if conn:
            await conn.close()


async def load_repo_agent_profiles(
    db_url: str,
    repos: list[dict] | None,
    sandbox_id: str = "",
) -> list[dict]:
    """Carrega agents cadastrados na sandbox por convenção ``<repo>-architect``."""
    if not db_url or not repos:
        return []
    resolved_sandbox_id = str(sandbox_id or _sandbox_id_for_repos(repos)).strip()
    if not resolved_sandbox_id:
        return []
    try:
        uuid.UUID(resolved_sandbox_id)
    except ValueError:
        return []
    agent_names = _agent_names_for_repos(repos)
    if not agent_names:
        return []

    conn: asyncpg.Connection | None = None
    try:
        conn = await asyncpg.connect(_asyncpg_dsn(db_url))
        rows = await conn.fetch(
            """
            SELECT name, description, system_prompt, model
            FROM sandbox_agents
            WHERE enabled = TRUE
              AND sandbox_id = $1::uuid
              AND lower(name) = ANY($2::text[])
            ORDER BY array_position($2::text[], lower(name))
            """,
            resolved_sandbox_id,
            agent_names,
        )
        return [
            {
                "slug": r["name"],
                "name": r["name"],
                "description": r["description"] or "",
                "system_prompt": str(r["system_prompt"] or "").strip(),
                "default_model": r["model"] or "",
            }
            for r in rows
        ]
    except Exception as exc:
        log.warning("load_repo_agent_profiles falhou: %s", exc)
        return []
    finally:
        if conn:
            await conn.close()


def _sandbox_id_for_repos(repos: list[dict]) -> str:
    for repo in repos:
        sandbox_id = str(repo.get("sandbox_id") or "").strip()
        if sandbox_id:
            return sandbox_id
    return ""


def _agent_names_for_repos(repos: list[dict]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for repo in repos:
        raw_slug = str(repo.get("slug") or repo.get("alias") or "").strip()
        if not raw_slug:
            continue
        name_part = _normalise_agent_name_part(raw_slug)
        if not name_part:
            continue
        agent_name = f"{name_part}-architect"
        if agent_name not in seen:
            seen.add(agent_name)
            out.append(agent_name)
    return out


def _normalise_agent_name_part(value: str) -> str:
    normalised = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower())
    return normalised.strip("-_")


def build_prompt_with_agent(
    user_message: str,
    skills: list[dict],
    sandbox_session_url: str,
    repos: list[dict] | None = None,
    session_root: str = "",
    agent_profiles: list[dict] | None = None,
    execution_profile: str = "medium",
    native_subagents: bool = False,
) -> str:
    """Monta o prompt do turno: só o que muda por sessão + a mensagem do usuário.

    As regras fixas ficam no CLAUDE.md base (memória do usuário). Inclui o
    caminho absoluto do worktree (workaround para bug de CWD do openclaude), o
    índice das skills do repositório e as ferramentas do servidor de sessão.
    ``native_subagents``: o runtime carrega ``~/.claude/agents`` (Claude CLI),
    então o perfil do arquiteto é citado, não colado.
    """
    parts: list[str] = []

    worktree_paths: list[str] = []
    for r in [r for r in repos or [] if not r.get("read_only")]:  # read_only: seção workspace
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
            "Use sempre estes caminhos absolutos em Bash/Grep e comandos de leitura "
            "via Bash, como `sed -n`, `nl -ba` ou `cat` "
            "(não confies em `pwd`):\n" + wt_str
        )

    if agent_profiles:
        parts.append(render_repo_agents(agent_profiles, native_subagents=native_subagents))


    if skills:
        parts.append(render_repo_skills(skills))

    if sandbox_session_url:
        parts.append(render_session_tools(sandbox_session_url, repos))

    parts.append(render_execution_profile(execution_profile))

    parts.append("## Mensagem do utilizador\n\n" + user_message)

    return "\n\n---\n\n".join(parts)
