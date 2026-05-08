"""Listagem de outros repositórios disponíveis no sandbox.

Permite ao agente fazer investigação cruzada read-only entre repos da empresa
sem inflar o contexto principal (extraído de ``_agent_context.py``).
"""

from __future__ import annotations

import logging
import os

import httpx

log = logging.getLogger(__name__)

_OTHER_REPOS_LIMIT = int(os.getenv("OTHER_REPOS_LIMIT", "20"))


async def fetch_other_repos(
    session_url: str,
    repos: list[dict] | None,
    limit: int = _OTHER_REPOS_LIMIT,
) -> list[str]:
    """Lista repos clonados em ``/repos/`` que NÃO são o(s) da sessão actual.

    Retorna apenas slugs (não paths completos) para evitar context bloat.
    Tolerante a falhas: ``[]`` em qualquer erro — o agente segue só com o
    worktree da sessão.
    """
    if not session_url:
        return []
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{session_url.rstrip('/')}/repos/list")
        if resp.status_code != 200:
            return []
        all_repos: list[str] = resp.json().get("repos") or []
    except Exception as exc:  # noqa: BLE001 - degrada graciosamente
        log.debug("repos/list falhou: %s", exc)
        return []

    session_slugs = {
        str(r.get("slug") or r.get("alias") or "").lower() for r in (repos or [])
    }
    others = [slug for slug in all_repos if slug and slug.lower() not in session_slugs]
    return sorted(others)[:limit]


def render_other_repos_section(other_repos: list[str]) -> str:
    """Bloco markdown listando outros repos disponíveis em ``/repos/``."""
    if not other_repos:
        return ""
    listing = "\n".join(f"- `/repos/{slug}/`" for slug in other_repos)
    return (
        "## Outros repositórios disponíveis (read-only)\n\n"
        "Estes repos estão clonados no container e podem ser inspecionados "
        "para investigação cruzada. **Não os modifique** (são compartilhados "
        "entre sessões); use apenas `Read`, `Grep`, `Glob` e `Bash` "
        "(`ls`, `cat`, `wc`):\n\n" + listing
    )
