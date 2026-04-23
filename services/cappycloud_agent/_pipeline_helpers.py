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
    """Injeta comandos /add para cada worktree antes da mensagem do utilizador.

    Apenas relevante em sessões **multi-repo** (>1 repo): cada repo recebe um
    ``/add <path>`` para o openclaude conseguir navegar entre os repositórios.
    """
    if not repos or not session_root:
        return user_message
    if len(repos) <= 1:
        return user_message

    add_lines: list[str] = []
    for repo in repos:
        alias = repo.get("alias") or repo.get("slug", "")
        if not alias:
            continue
        wt_path = repo.get("worktree_path") or f"{session_root}/{alias}"
        add_lines.append(f"/add {wt_path}")
        log.debug("Injecting /add %s", wt_path)

    if not add_lines:
        return user_message

    return "\n".join(add_lines) + "\n\n" + user_message
