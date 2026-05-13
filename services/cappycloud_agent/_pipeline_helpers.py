import json
import logging
import os


log = logging.getLogger(__name__)


def db_url() -> str:
    explicit = os.getenv("PIPELINE_DATABASE_URL", "").strip()
    if explicit:
        return explicit
    return os.getenv("DATABASE_URL", "").replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )


def sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def inject_repo_context(user_message: str, repos: list, session_root: str) -> str:
    """No-op: anteriormente injetava /add <path> para multi-repo.

    Removido porque o openclaude interpreta ``/add`` como slash command
    interativo e encerra o turno com 0 tokens quando o recebe no prompt
    de texto — causando o erro "O agente não conseguiu iniciar a sessão".

    Os caminhos absolutos dos worktrees já são passados via
    ``build_prompt_with_agent`` (seção "## Worktree") e o CLAUDE.md do
    sandbox instrui o agente a usar esses paths directamente.
    """
    return user_message


async def build_prompt_with_worktree_context(
    prompt: str,
    sandbox_session_url: str,
    repos: list[dict],
    session_root: str | None,
) -> str:
    """Injeta snapshot do worktree no prompt. Degrada graciosamente em caso de erro."""
    if not repos:
        return prompt
    try:
        from ._agent_context import (
            fetch_worktree_top_levels,
            render_worktree_top_level_section,
            inject_section_before_user_message,
        )

        top_level = await fetch_worktree_top_levels(
            sandbox_session_url, repos, session_root or ""
        )
        section = render_worktree_top_level_section(top_level)
        if section:
            return inject_section_before_user_message(prompt, section)
    except Exception as exc:  # noqa: BLE001
        log.warning("[Dispatcher] worktree top-level fetch falhou: %s", exc)
    return prompt
