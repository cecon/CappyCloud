"""Repositórios da conversa (diff/arquivos/PR) e alvo do PR por provedor."""

from __future__ import annotations

import json

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


class _Result:
    def __init__(self, row=None, items=()):
        self._row, self._items = row, list(items)

    def fetchone(self):
        return self._row

    def scalars(self):
        return iter(self._items)


class _FakeDb:
    def __init__(self, row, catalog=()):
        self._results = [_Result(row=row), _Result(items=catalog)]

    async def execute(self, *_args, **_kwargs):
        return self._results.pop(0)


async def test_carrega_repos_do_workspace_com_dados_do_catalogo() -> None:
    import uuid
    from types import SimpleNamespace

    from app.adapters.primary.http.conversation_repos import load_conversation_repos

    cid = uuid.uuid4()
    conv_repos = [
        {"slug": "seller", "alias": "backend", "base_branch": "develop"},
        {"slug": "docs", "alias": "docs", "read_only": True, "worktree_path": "/ws/repos/docs"},
    ]
    session = json.dumps([{"alias": "backend", "worktree_path": "/s/backend"}])
    provider = uuid.uuid4()
    catalog = [SimpleNamespace(slug="seller", clone_url="https://g/seller", provider_id=provider)]
    row = (conv_repos, "/repos/workspaces/loja/sessions/abc", uuid.uuid4(), session)

    conv = await load_conversation_repos(_FakeDb(row, catalog), cid, "user")

    assert conv.prefixed is True
    backend, docs = conv.repos
    assert (backend.worktree_path, backend.base_branch) == ("/s/backend", "develop")
    assert (backend.clone_url, backend.provider_id) == ("https://g/seller", provider)
    assert docs.read_only and docs.worktree_path == "/ws/repos/docs"
    assert conv.editable == [backend]


async def test_conversa_sem_repos_usa_a_pasta_da_sessao() -> None:
    import uuid

    from app.adapters.primary.http.conversation_repos import load_conversation_repos

    cid = uuid.uuid4()
    conv = await load_conversation_repos(_FakeDb(([], None, None, None)), cid, "user")
    assert conv.prefixed is False
    assert conv.repos[0].worktree_path == f"/repos/sessions/{cid.hex[:12]}"


async def test_conversa_de_outro_usuario_da_404() -> None:
    import uuid

    from app.adapters.primary.http.conversation_repos import load_conversation_repos

    with pytest.raises(HTTPException) as exc:
        await load_conversation_repos(_FakeDb(None), uuid.uuid4(), "user")
    assert exc.value.status_code == 404
