"""Servidor MCP `cappy` do sandbox: protocolo e repasse do contexto da conversa."""

from __future__ import annotations

import json

import pytest

from tests.unit.agent_runtime_test_loader import ROOT, load_agent_module

_server = load_agent_module(
    "sandbox_evidence_mcp_server", ROOT / "services/sandbox/evidence_mcp_server.py"
)
_CONTEXT = {
    "repos": [{"slug": "seller"}],
    "session_root": "/repos/workspaces/loja/sessions/abc",
    "session_url": "http://127.0.0.1:8080",
}


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, dict]]:
    seen: list[tuple[str, str, dict]] = []

    async def evidence(question, **kwargs):
        seen.append(("evidencias", question, kwargs))
        return "- /repos/x/a.py"

    async def knowledge(question, **kwargs):
        seen.append(("conhecimento", question, kwargs))
        return "- fato"

    monkeypatch.setattr(_server, "_tool_functions", lambda: (evidence, knowledge))
    return seen


def _call(name: str, arguments: dict) -> dict:
    message = {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    response = _server.handle(message, _CONTEXT)
    assert response is not None
    return response


def test_lista_as_duas_ferramentas() -> None:
    response = _server.handle({"id": 1, "method": "tools/list"}, _CONTEXT)
    assert response is not None
    names = [tool["name"] for tool in response["result"]["tools"]]
    assert names == ["buscar_evidencias", "consultar_conhecimento_workspace"]
    assert _server.handle({"method": "notifications/initialized"}, _CONTEXT) is None


def test_buscar_evidencias_repassa_o_contexto(calls) -> None:
    response = _call("buscar_evidencias", {"pergunta": "onde sai a CBS?", "com_trechos": True})

    assert response["result"]["content"][0]["text"] == "- /repos/x/a.py"
    kind, question, kwargs = calls[0]
    assert (kind, question) == ("evidencias", "onde sai a CBS?")
    assert kwargs == {
        "session_url": "http://127.0.0.1:8080",
        "repos": [{"slug": "seller"}],
        "session_root": "/repos/workspaces/loja/sessions/abc",
        "with_excerpts": True,
    }


def test_conhecimento_do_workspace(calls) -> None:
    response = _call("consultar_conhecimento_workspace", {"pergunta": "CBS"})

    assert response["result"]["content"][0]["text"] == "- fato"
    assert calls[0][0] == "conhecimento"


def test_pergunta_vazia_e_ferramenta_desconhecida(calls) -> None:
    assert _call("buscar_evidencias", {"pergunta": "  "})["result"]["isError"] is True
    assert _call("apagar_tudo", {})["error"]["code"] == -32601
    assert calls == []


def test_contexto_vem_do_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "CAPPY_TOOL_CONTEXT", json.dumps({"repos": [{"slug": "a"}, "x"], "session_root": "/r"})
    )
    monkeypatch.setenv("SESSION_SERVER_PORT", "9090")
    assert _server._context() == {
        "repos": [{"slug": "a"}],
        "session_root": "/r",
        "session_url": "http://127.0.0.1:9090",
    }
    monkeypatch.setenv("CAPPY_TOOL_CONTEXT", "{quebrado")
    assert _server._context()["repos"] == []
