"""Repositórios da conversa (diff/arquivos/PR) e alvo do PR por provedor."""

from __future__ import annotations

import pytest
from app.adapters.primary.http.conversation_repos import (
    ConversationRepo,
    ConversationRepos,
    _json_list,
    _merge,
)
from app.infrastructure.git_pull_requests import PullRequestError, parse_pr_target
from fastapi import HTTPException

_BACKEND = ConversationRepo(
    "backend", "seller", "/repos/workspaces/loja/sessions/a/backend", "main"
)
_DOCS = ConversationRepo(
    "docs", "docs", "/repos/workspaces/loja/repos/docs", "main", read_only=True
)


def test_workspace_prefixa_caminhos_pelo_alias() -> None:
    conv = ConversationRepos([_BACKEND, _DOCS], prefixed=True)
    assert conv.to_ui_path(_BACKEND, "src/app.py") == "backend/src/app.py"
    assert conv.from_ui_path("docs/README.md") == (_DOCS, "README.md")
    assert conv.editable == [_BACKEND]
    with pytest.raises(HTTPException):
        conv.from_ui_path("outro/x.py")
    with pytest.raises(HTTPException):
        conv.from_ui_path("backend")


def test_conversa_legada_mantem_caminhos_sem_prefixo() -> None:
    conv = ConversationRepos([_BACKEND], prefixed=False)
    assert conv.to_ui_path(_BACKEND, "src/app.py") == "src/app.py"
    assert conv.from_ui_path("src/app.py") == (_BACKEND, "src/app.py")


def test_sessao_do_agente_completa_dados_da_conversa() -> None:
    conv = [{"slug": "seller", "alias": "backend", "base_branch": "develop"}]
    session = [{"alias": "backend", "worktree_path": "/wt/backend", "branch_name": ""}]
    merged = _merge(conv, session)
    assert merged == [
        {
            "slug": "seller",
            "alias": "backend",
            "base_branch": "develop",
            "worktree_path": "/wt/backend",
        }
    ]
    assert _json_list('"[{\\"slug\\": \\"x\\"}]"') == [{"slug": "x"}]
    assert _json_list(None) == []


@pytest.mark.parametrize(
    ("url", "provider", "path"),
    [
        ("https://github.com/acme/loja.git", "github", "acme/loja"),
        ("git@github.com:acme/loja.git", "github", "acme/loja"),
        ("https://org@dev.azure.com/org/Proj/_git/Seller", "azure_devops", "org/Proj/Seller"),
        ("https://org.visualstudio.com/Proj/_git/Seller", "azure_devops", "org/Proj/Seller"),
    ],
)
def test_alvo_do_pr_pela_url_de_clone(url: str, provider: str, path: str) -> None:
    target = parse_pr_target(url)
    assert (target.provider, target.repo_path) == (provider, path)


def test_provedor_nao_suportado() -> None:
    with pytest.raises(PullRequestError):
        parse_pr_target("https://gitlab.com/acme/loja.git")
