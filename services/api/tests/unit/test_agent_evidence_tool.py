"""Busca prévia como ferramenta: devolve só nomes, e o modelo decide o que abrir."""

from __future__ import annotations

import json

import httpx
import pytest

from tests.unit.agent_runtime_test_loader import ROOT, load_agent_module

for _name in ("_knowledge_search", "_workspace_paths"):
    load_agent_module(
        f"services.cappycloud_agent.{_name}",
        ROOT / f"services/cappycloud_agent/{_name}.py",
    )
_tool = load_agent_module(
    "services.cappycloud_agent._evidence_tool",
    ROOT / "services/cappycloud_agent/_evidence_tool.py",
)
_REAL_CLIENT = httpx.AsyncClient
_ROOT = "/repos/workspaces/loja/sessions/abc"
_REPOS = [
    {
        "slug": "seller",
        "worktree_path": f"{_ROOT}/seller",
        "confluence_url": "https://share.example.com",
        "confluence_space": "Postos",
    }
]
_QUESTION = 'Onde o "ProdIndCbs" é calculado?'


def _patch_http(monkeypatch: pytest.MonkeyPatch, handler) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def recording(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    def factory(*_args, **kwargs):
        return _REAL_CLIENT(transport=httpx.MockTransport(recording), timeout=kwargs.get("timeout"))

    monkeypatch.setattr(_tool.httpx, "AsyncClient", factory)
    return seen


def _sandbox(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/worktree/search":
        query = json.loads(request.content)["query"]
        return httpx.Response(
            200,
            json={
                "matches": [
                    {"path": "src/fiscal/cbs.py", "line": 12, "text": f"def calc_{query}():"},
                    {"path": "src/fiscal/cbs.py", "line": 40, "text": f"{query} = True"},
                    {"path": "src/model/prod.py", "line": 7, "text": f"{query}: bool"},
                ]
            },
        )
    if request.url.path == "/confluence/search":
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "Reforma tributária - CBS",
                        "url": "https://share.example.com/pages/1",
                        "summary": "texto longo da página",
                    }
                ]
            },
        )
    return httpx.Response(404, json={})


async def test_devolve_so_nomes_de_arquivo_e_documento(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_http(monkeypatch, _sandbox)
    text = await _tool.find_evidence(
        _QUESTION, session_url="http://127.0.0.1:8080", repos=_REPOS, session_root=_ROOT
    )

    assert "## Código (2 arquivos)" in text
    # Caminho absoluto, pronto para o Read; um arquivo por linha, sem repetir.
    assert f"- {_ROOT}/seller/src/fiscal/cbs.py (termos:" in text
    assert text.count("src/fiscal/cbs.py") == 1
    assert "- [Confluence] Reforma tributária - CBS — https://share.example.com/pages/1" in text
    # Sem trechos: nem a linha do código nem o resumo da página.
    assert "def calc_" not in text
    assert "texto longo" not in text


async def test_com_trechos_mostra_linha_e_resumo(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_http(monkeypatch, _sandbox)
    text = await _tool.find_evidence(
        _QUESTION,
        session_url="http://127.0.0.1:8080",
        repos=_REPOS,
        session_root=_ROOT,
        with_excerpts=True,
    )

    assert "    12: def calc_" in text
    assert "texto longo da página" in text


async def test_sem_termos_nao_chama_o_sandbox(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _patch_http(monkeypatch, _sandbox)
    text = await _tool.find_evidence(
        "ok", session_url="http://127.0.0.1:8080", repos=_REPOS, session_root=_ROOT
    )

    assert "Nenhum termo pesquisável" in text
    assert seen == []


async def test_nada_encontrado_e_dito_claramente(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_http(monkeypatch, lambda _r: httpx.Response(200, json={"matches": [], "results": []}))
    text = await _tool.find_evidence(
        _QUESTION, session_url="http://127.0.0.1:8080", repos=_REPOS, session_root=_ROOT
    )

    assert "Nada encontrado no código nem na documentação" in text


async def test_conhecimento_do_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/memory/search":
            return httpx.Response(
                200,
                json={
                    "results": [{"content": "CBS sai de cbs.py", "files": ["src/fiscal/cbs.py"]}]
                },
            )
        return httpx.Response(200, json={"text": "calc_cbs -> cbs.py"})

    seen = _patch_http(monkeypatch, handler)
    text = await _tool.find_workspace_knowledge(
        "onde sai a CBS?", session_url="http://127.0.0.1:8080", session_root=_ROOT
    )

    assert "- CBS sai de cbs.py (arquivos: src/fiscal/cbs.py)" in text
    assert "calc_cbs -> cbs.py" in text
    assert {r.url.path for r in seen} == {"/memory/search", "/workspaces/loja/knowledge/query"}


async def test_conhecimento_fora_de_workspace_nao_consulta(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _patch_http(monkeypatch, _sandbox)
    text = await _tool.find_workspace_knowledge(
        "onde sai a CBS?", session_url="http://127.0.0.1:8080", session_root="/repos/sessions/abc"
    )

    assert "não está em um workspace" in text
    assert seen == []


def test_contexto_da_ferramenta_so_tem_tipos_json() -> None:
    import uuid

    repo_id = uuid.uuid4()
    context = _tool.evidence_tool_context(
        [{"slug": "seller", "repo_id": repo_id, "confluence_labels": ("a", "b"), "token": "x"}],
        _ROOT,
    )

    assert context == {
        "repos": [{"slug": "seller", "repo_id": str(repo_id), "confluence_labels": ["a", "b"]}],
        "session_root": _ROOT,
    }
    json.dumps(context)
