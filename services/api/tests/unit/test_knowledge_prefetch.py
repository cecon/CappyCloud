"""Memória e grafo do workspace consultados pela API e injetados no prompt."""

from __future__ import annotations

import sys

import httpx
import pytest

from tests.unit.agent_runtime_test_loader import ROOT, load_agent_module


def _load():
    """Carrega o módulo com as dependências reais, sem depender da ordem da suíte."""
    names = ("_agent_context", "_workspace_paths")
    saved = {n: sys.modules.get(f"services.cappycloud_agent.{n}") for n in names}
    try:
        for name in names:
            load_agent_module(
                f"services.cappycloud_agent.{name}",
                ROOT / f"services/cappycloud_agent/{name}.py",
            )
        return load_agent_module(
            "services.cappycloud_agent._knowledge_prefetch",
            ROOT / "services/cappycloud_agent/_knowledge_prefetch.py",
        )
    finally:
        for name, module in saved.items():
            key = f"services.cappycloud_agent.{name}"
            if module is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = module


_kp = _load()
_REAL_CLIENT = httpx.AsyncClient
_SESSION = "/repos/workspaces/proteus/sessions/abc"
_PROMPT = "[contexto]\n\n## Mensagem do utilizador\nonde o RPS vai para o TSS?"


def _patch_http(monkeypatch: pytest.MonkeyPatch, handler) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def recording(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    def factory(*_args, **kwargs):
        return _REAL_CLIENT(transport=httpx.MockTransport(recording), timeout=kwargs.get("timeout"))

    monkeypatch.setattr(_kp.httpx, "AsyncClient", factory)
    return seen


def _sandbox(memories: list[dict], graph: str, status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/memory/search":
            return httpx.Response(status, json={"results": memories})
        return httpx.Response(status, json={"text": graph})

    return handler


def test_question_text_tira_o_contexto_e_limita() -> None:
    assert _kp.question_text(_PROMPT) == "onde o RPS vai para o TSS?"
    assert _kp.question_text("  a\n  b  ") == "a b"
    assert len(_kp.question_text("x" * 301)) == 300
    assert _kp.question_text("   ") == ""


def test_secao_vazia_sem_achados() -> None:
    assert _kp.render_knowledge_section([], "") == ""


def test_secao_limita_memorias_e_texto() -> None:
    memories = [
        {"type": "fact", "content": f"fato {i} " + "y" * 600, "files": ["a", "b", "c", "d"]}
        for i in range(6)
    ]
    section = _kp.render_knowledge_section(memories, "g" * 3000)
    bullets = [line for line in section.splitlines() if line.startswith("- [fact]")]
    assert len(bullets) == 4
    assert bullets[0].endswith("(arquivos: a, b, c)")
    assert len(bullets[0].split(" (arquivos")[0]) == len("- [fact] ") + 500
    assert section.endswith("g" * 2500)
    assert "g" * 2501 not in section


async def test_injeta_memoria_e_grafo_antes_da_mensagem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    memories = [
        {"type": "fact", "content": "Lote vai ao TSS em TSSEnvLote", "files": ["TSSNFSE.prw"]}
    ]
    seen = _patch_http(monkeypatch, _sandbox(memories, "NODE TSSEnvLote"))

    prompt = await _kp.inject_workspace_knowledge(
        _PROMPT,
        user_message=_PROMPT,
        sandbox_session_url="http://sb:8080/",
        session_root=_SESSION,
    )

    head, message = prompt.split("## Mensagem do utilizador")
    assert head.startswith("[contexto]")
    assert "- [fact] Lote vai ao TSS em TSSEnvLote (arquivos: TSSNFSE.prw)" in head
    assert "NODE TSSEnvLote" in head
    assert message == "\nonde o RPS vai para o TSS?"
    by_path = {r.url.path: r for r in seen}
    assert by_path["/memory/search"].url.params["workspace"] == "proteus"
    assert by_path["/memory/search"].url.params["q"] == "onde o RPS vai para o TSS?"
    query = by_path["/workspaces/proteus/knowledge/query"].url.params
    assert query["q"] == "onde o RPS vai para o TSS?"
    assert query["budget"] == "600"


async def test_sessao_retomada_recebe_a_secao_antes_da_pergunta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_http(monkeypatch, _sandbox([], "NODE X"))
    prompt = await _kp.inject_workspace_knowledge(
        "e o lote?",
        user_message="e o lote?",
        sandbox_session_url="http://sb",
        session_root=_SESSION,
    )
    assert prompt.startswith("## Conhecimento do workspace")
    assert prompt.endswith("---\n\ne o lote?")
    assert "### Memória" not in prompt


@pytest.mark.parametrize(
    ("session_root", "url", "message"),
    [
        ("/repos/sessions/abc", "http://sb", "pergunta"),  # não é workspace
        (_SESSION, "", "pergunta"),
        (_SESSION, "http://sb", "   "),
    ],
)
async def test_nao_consulta_sem_workspace_url_ou_pergunta(
    monkeypatch: pytest.MonkeyPatch, session_root: str, url: str, message: str
) -> None:
    seen = _patch_http(monkeypatch, _sandbox([{"content": "x"}], "g"))
    prompt = await _kp.inject_workspace_knowledge(
        "p", user_message=message, sandbox_session_url=url, session_root=session_root
    )
    assert prompt == "p"
    assert seen == []


async def test_falha_ou_resposta_vazia_nao_muda_o_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_http(monkeypatch, _sandbox([{"content": "x"}], "g", status=503))
    args = {"user_message": "q", "sandbox_session_url": "http://sb", "session_root": _SESSION}
    assert await _kp.inject_workspace_knowledge("p", **args) == "p"

    _patch_http(monkeypatch, _sandbox([{"content": "   "}], "  "))
    assert await _kp.inject_workspace_knowledge("p", **args) == "p"

    def boom(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sandbox fora")

    _patch_http(monkeypatch, boom)
    assert await _kp.inject_workspace_knowledge("p", **args) == "p"
