"""Validação do worktree antes de iniciar a sessão gRPC.

Garante que o openclaude não recebe um ``working_directory`` inexistente,
evitando o sintoma "tudo verde + erro genérico logo a seguir".
"""

from __future__ import annotations

import logging
from typing import Optional

import asyncpg

from ._agent_context import (
    fetch_worktree_top_levels,
    inject_section_before_user_message,
    render_worktree_top_level_section,
)
from ._grpc_helpers import build_worktree_missing_error
from ._task_events import insert_error_event, update_task_status

log = logging.getLogger(__name__)


async def validate_and_inject_worktree(
    *,
    pool: Optional[asyncpg.Pool],
    task_id: str,
    prompt: str,
    repos: list,
    sandbox_session_url: str,
    session_root: str,
    working_directory: str,
) -> str | None:
    """Confirma que existe worktree e devolve o prompt enriquecido.

    Em caso de falha, regista o erro detalhado e devolve ``None`` — o
    chamador deve abortar o dispatch.
    """
    slugs = [str(r.get("slug") or r.get("alias") or "?") for r in repos]
    try:
        top_level = await fetch_worktree_top_levels(
            sandbox_session_url, repos, session_root
        )
    except Exception as exc:  # noqa: BLE001 — capturado para reportar
        log.exception("[Worktree] fetch falhou para task %s", task_id[:8])
        await update_task_status(pool, task_id, "error")
        await insert_error_event(
            pool,
            task_id,
            build_worktree_missing_error(
                repo_slugs=slugs,
                working_directory=working_directory,
                detail=str(exc),
            ),
        )
        return None

    if not any(top_level.values()):
        log.warning(
            "[Worktree] Vazio para task %s (repos=%s, wd=%s)",
            task_id[:8],
            slugs,
            working_directory,
        )
        await update_task_status(pool, task_id, "error")
        await insert_error_event(
            pool,
            task_id,
            build_worktree_missing_error(
                repo_slugs=slugs, working_directory=working_directory
            ),
        )
        return None

    section = render_worktree_top_level_section(top_level)
    if section:
        prompt = inject_section_before_user_message(prompt, section)

    return prompt
