"""Sessões de workspace: raiz, diretório de trabalho e contexto do prompt."""

from __future__ import annotations

from tests.unit.agent_runtime_test_loader import ROOT, load_agent_module

_paths = load_agent_module(
    "services.cappycloud_agent._workspace_paths",
    ROOT / "services/cappycloud_agent/_workspace_paths.py",
)
_store = load_agent_module(
    "services.cappycloud_agent._session_store",
    ROOT / "services/cappycloud_agent/_session_store.py",
)

_WS_SESSION = "/repos/workspaces/loja/sessions/abc123"
_REPOS = [{"slug": "Seller", "alias": "backend", "worktree_path": f"{_WS_SESSION}/backend"}]


def test_reconhece_sessao_de_workspace() -> None:
    assert _paths.workspace_root_of(_WS_SESSION) == "/repos/workspaces/loja"
    assert _paths.workspace_root_of(_WS_SESSION + "/") == "/repos/workspaces/loja"
    for other in ("/repos/sessions/abc", "/repos/workspaces/loja", "", None):
        assert _paths.workspace_root_of(other) is None


def test_sessao_de_workspace_trabalha_na_pasta_da_sessao_mesmo_com_um_repo() -> None:
    record = _store.SandboxRecord(
        user_id="u",
        chat_id="c",
        grpc_host="sandbox",
        grpc_port=50051,
        session_root=_WS_SESSION,
        repos=_REPOS,
    )
    assert record.working_directory == _WS_SESSION

    legacy = _store.SandboxRecord(
        user_id="u",
        chat_id="c",
        grpc_host="sandbox",
        grpc_port=50051,
        session_root="/repos/sessions/abc",
        repos=[{"slug": "Seller", "alias": "Seller"}],
    )
    assert legacy.working_directory == "/repos/sessions/abc/Seller"


def test_secao_do_prompt_lista_repos_e_conhecimento_somente_leitura() -> None:
    section = _paths.render_workspace_section(_WS_SESSION, _REPOS)
    assert "`backend` → `/repos/workspaces/loja/sessions/abc123/backend`" in section
    assert "/repos/workspaces/loja/knowledge/" in section
    assert "Somente leitura" in section
    assert _paths.render_workspace_section("/repos/sessions/abc", _REPOS) == ""
