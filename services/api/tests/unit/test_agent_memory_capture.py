"""Gravação automática da memória do workspace ao fim do turno."""

from __future__ import annotations

import json

import httpx
import pytest

from tests.unit.agent_runtime_test_loader import ROOT, load_agent_module

load_agent_module(
    "services.cappycloud_agent._workspace_paths",
    ROOT / "services/cappycloud_agent/_workspace_paths.py",
)
_capture = load_agent_module(
    "services.cappycloud_agent._memory_capture",
    ROOT / "services/cappycloud_agent/_memory_capture.py",
)

_WS = "/repos/workspaces/proteus/sessions/abc123"


def _for(**overrides):
    values = {
        "session_url": "http://sandbox:8080",
        "session_root": _WS,
        "question": "onde o RPS vai para o TSS?",
        "model": "claude-sonnet-5",
        "claude_cli": True,
    }
    return _capture.memory_capture_for(**{**values, **overrides})


def test_so_captura_sessao_de_workspace_no_claude_cli() -> None:
    capture = _for()
    assert capture is not None and capture.workspace == "proteus"
    assert capture.provider is None
    assert _for(claude_cli=False) is None
    assert _for(session_root="/repos/sessions/abc") is None
    assert _for(question="  ") is None


def test_openclaude_captura_com_provider_anthropic() -> None:
    azure = {
        "claude_cli": False,
        "provider_base_url": "https://r.services.ai.azure.com/api/projects/p/openai/v1",
        "provider_api_key": "k",
        "provider_api_format": "anthropic",
    }
    capture = _for(**azure)

    assert capture is not None and capture.workspace == "proteus"
    assert capture.provider == {"base_url": azure["provider_base_url"], "api_key": "k"}
    assert _for(**{**azure, "provider_api_format": "responses"}) is None
    assert _for(**{**azure, "provider_api_key": ""}) is None


async def test_envia_pergunta_resposta_e_modelo_ao_sandbox(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["token"] = request.headers.get("X-Internal-Token")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"saved": 2})

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        _capture.httpx, "AsyncClient", lambda **kw: real_client(transport=transport, **kw)
    )
    monkeypatch.setenv("INTERNAL_API_TOKEN", "segredo")

    saved = await _capture.capture_turn_memory(_for(), "Em TSSNFSE.prw, função TSSEnvLote.")

    assert saved == 2
    assert seen["url"] == "http://sandbox:8080/memory/extract"
    assert seen["token"] == "segredo"
    assert seen["body"] == {
        "workspace": "proteus",
        "question": "onde o RPS vai para o TSS?",
        "answer": "Em TSSNFSE.prw, função TSSEnvLote.",
        "model": "claude-sonnet-5",
    }


async def test_erro_no_sandbox_nao_quebra_o_turno(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(500, json={"error": "x"}))
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        _capture.httpx, "AsyncClient", lambda **kw: real_client(transport=transport, **kw)
    )

    assert await _capture.capture_turn_memory(_for(), "resposta") == 0
    assert await _capture.capture_turn_memory(_for(), "   ") == 0


async def test_openclaude_manda_o_provider_ao_sandbox(monkeypatch: pytest.MonkeyPatch) -> None:
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"saved": 1})

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        _capture.httpx, "AsyncClient", lambda **kw: real_client(transport=transport, **kw)
    )
    capture = _for(
        claude_cli=False,
        model="claude-opus-5-5",
        provider_base_url="https://r.services.ai.azure.com/api/projects/p/openai/v1",
        provider_api_key="k",
        provider_api_format="anthropic",
    )

    assert await _capture.capture_turn_memory(capture, "resposta") == 1
    assert bodies[0]["model"] == "claude-opus-5-5"
    assert bodies[0]["provider"] == {
        "base_url": "https://r.services.ai.azure.com/api/projects/p/openai/v1",
        "api_key": "k",
    }
