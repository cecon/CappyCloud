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
# O agente roda no mesmo container do session_server (porta fixa nos stacks).
_MEMORY_URL = "http://127.0.0.1:8080/memory"


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
    slug = posixpath.basename(root)
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
        lines.append(
            "Repositórios somente leitura (leia com Read ou Bash só de leitura: rg, grep, find,"
            " cat, sed -n; sem alterações nem PR):"
        )
        lines += read_only
    lines += [
        "Somente leitura (compartilhado do workspace; não edite):",
        f"- Instruções: `{root}/CLAUDE.md`",
        f"- Conhecimento: `{root}/knowledge/`",
        f"- Memória: `{root}/memory/`",
        "Edite apenas dentro dos worktrees listados acima.",
        "",
        "Grafo de código do workspace (graphify, gerado da branch principal de cada "
        "repositório): use-o para localizar módulos, dependências e quem chama o quê "
        "antes de buscas amplas. Pode não refletir mudanças desta conversa.",
        f"- `graphify query \"<pergunta>\" --graph {root}/knowledge/graphify/graph.json "
        "--budget 1500`",
        f"- `graphify explain \"<símbolo>\" --graph {root}/knowledge/graphify/graph.json`",
        f"- Visão geral por repositório: `{root}/knowledge/graphify/<alias>/GRAPH_REPORT.md`",
        "Se o arquivo do grafo não existir, siga sem ele.",
        "",
        "Memória do workspace (compartilhada entre as conversas deste workspace): busque "
        "antes de investigar do zero e grave o que valer para as próximas conversas "
        "(decisão, causa de bug, regra confirmada no código). Não grave segredos nem dados "
        "de clientes.",
        f"- Buscar: `curl -s -G {_MEMORY_URL}/search --data-urlencode workspace={slug} "
        "--data-urlencode 'q=<termos>'` (sem resultados = nada gravado sobre isso)",
        f"- Gravar: `curl -s -X POST {_MEMORY_URL}/save -H 'Content-Type: application/json' "
        f"-d '{{\"workspace\":\"{slug}\",\"type\":\"fact\",\"content\":\"<o que lembrar>\","
        "\"files\":\"<alias>/<caminho relativo>\"}'` (type: fact, bug, architecture, pattern, workflow "
        "ou preference)",
        "Se a memória responder erro, siga sem ela.",
    ]
    return "\n".join(lines)
