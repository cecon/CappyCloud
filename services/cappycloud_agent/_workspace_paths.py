"""Caminhos de sessões de workspace no sandbox.

Sessão de workspace: ``/repos/workspaces/<slug>/sessions/<id>/`` com um
worktree por repositório. O agente trabalha na pasta da sessão (não num
worktree isolado) e herda o ``CLAUDE.md`` da raiz do workspace.
"""

from __future__ import annotations

import posixpath
import re

WORKSPACES_ROOT = "/repos/workspaces"
_SESSION_RE = re.compile(r"^/repos/workspaces/([a-z0-9][a-z0-9-]{1,62})/sessions/[^/]+$")


def workspace_root_of(session_root: str | None) -> str | None:
    """Raiz do workspace se ``session_root`` for uma sessão de workspace, senão ``None``."""
    normalized = posixpath.normpath(session_root or "")
    match = _SESSION_RE.match(normalized)
    return f"{WORKSPACES_ROOT}/{match.group(1)}" if match else None


def render_workspace_section(session_root: str, repos: list[dict]) -> str:
    """Seção do prompt que explica a estrutura do workspace ao agente."""
    root = workspace_root_of(session_root)
    if not root:
        return ""
    lines = [
        "## Workspace",
        f"Pasta de trabalho desta conversa: `{session_root}` (todos os repositórios abaixo).",
        "Repositórios (worktrees desta conversa, cada um na sua branch):",
    ]
    read_only: list[str] = []
    for repo in repos:
        alias = repo.get("alias") or repo.get("slug") or ""
        if repo.get("read_only"):
            read_only.append(f"- `{alias}` → `{root}/repos/{alias}` (consulta; não edite)")
            continue
        path = repo.get("worktree_path") or f"{session_root}/{alias}"
        lines.append(f"- `{alias}` → `{path}`")
    if read_only:
        lines.append("Repositórios somente leitura (use Read/Grep/Glob; sem alterações nem PR):")
        lines += read_only
    lines += [
        "Somente leitura (compartilhado do workspace; não edite):",
        f"- Instruções: `{root}/CLAUDE.md`",
        f"- Conhecimento: `{root}/knowledge/`",
        f"- Memória: `{root}/memory/`",
        "Edite apenas dentro dos worktrees listados acima.",
    ]
    return "\n".join(lines)
