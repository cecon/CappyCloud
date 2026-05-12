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
