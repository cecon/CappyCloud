"""Claude CLI com sessão retomada: o turno leva só a pergunta, sem recompor contexto."""

from __future__ import annotations

import sys
import types

import httpx
import pytest

from tests.unit.agent_runtime_test_loader import ROOT, load_agent_module

_DEPS = ("_evidence_prefetch", "_pipeline_helpers", "_worktree_validation")


def _load_task_context():
    """Carrega _task_context com dependências falsas só durante a importação.

    Outros testes trocam ``_agent_context`` no sys.modules por versões parciais;
    importar as dependências reais aqui dependeria da ordem da suíte. As funções
    usadas são substituídas por monkeypatch em cada teste, e o sys.modules volta
    a ser como era.
    """
    names = [f"services.cappycloud_agent.{dep}" for dep in _DEPS]
    saved = {name: sys.modules.get(name) for name in names}
    for name in names:
        stub = types.ModuleType(name)
        for attr in (
            "inject_evidence_prefetch",
            "add_workspace_section",
            "inject_repo_context",
            "validate_and_inject_worktree",
        ):
            setattr(stub, attr, None)
        sys.modules[name] = stub
    try:
        return load_agent_module(
            "services.cappycloud_agent._task_context",
            ROOT / "services/cappycloud_agent/_task_context.py",
        )
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


_context = _load_task_context()
_resume = load_agent_module(
    "services.cappycloud_agent._claude_cli_resume",
    ROOT / "services/cappycloud_agent/_claude_cli_resume.py",
)


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    seen = {"workspace": 0, "validate": 0, "evidence": 0, "add": 0}

    def workspace(prompt, *_args):
        seen["workspace"] += 1
        return prompt + "\n[workspace]"

    def add_lines(prompt, *_args):
        seen["add"] += 1
        return "/add /repos/x\n\n" + prompt

    async def validate(*, prompt, **_kwargs):
        seen["validate"] += 1
        return prompt + "\n[worktree ok]"

    async def evidence(prompt, **_kwargs):
        seen["evidence"] += 1
        return prompt + "\n[evidências]"

    monkeypatch.setattr(_context, "add_workspace_section", workspace)
    monkeypatch.setattr(_context, "inject_repo_context", add_lines)
    monkeypatch.setattr(_context, "validate_and_inject_worktree", validate)
    monkeypatch.setattr(_context, "inject_evidence_prefetch", evidence)
    return seen


async def _prepare(resumed: bool, phases: list, openclaude: bool = False) -> str | None:
    async def emit(task_id, stage, label, state, duration_ms=None):
        phases.append((label, state))

    return await _context.prepare_turn_prompt(
        emit_phase=emit,
        pool=None,
        task_id="t1",
        prompt="[instruções e contexto do pipeline]\n\nqual a versão do banco?",
        user_message="qual a versão do banco?",
        resumed_cli_session=resumed,
        sandbox_session_url="http://sandbox:8080",
        repos=[{"slug": "Seller"}],
        session_root="/repos/workspaces/loja/sessions/abc",
        working_directory="/repos/workspaces/loja/sessions/abc",
        openclaude=openclaude,
    )


async def test_sessao_retomada_manda_so_a_pergunta(calls: dict[str, int]) -> None:
    phases: list = []
    prompt = await _prepare(True, phases)
    assert prompt == "qual a versão do banco?"
    # Worktree continua conferido; estrutura e evidências não são recalculadas.
    assert calls == {"workspace": 0, "validate": 1, "evidence": 0, "add": 0}
    assert phases == [("Retomando a sessão", "active"), ("Sessão retomada", "done")]


async def test_primeira_mensagem_leva_o_contexto_completo(calls: dict[str, int]) -> None:
    phases: list = []
    prompt = await _prepare(False, phases)
    assert "[instruções e contexto do pipeline]" in prompt
    assert prompt.endswith("[workspace]\n[worktree ok]\n[evidências]")
    assert calls == {"workspace": 1, "validate": 1, "evidence": 1, "add": 0}
    assert phases[-1] == ("Contexto preparado", "done")


async def test_add_so_vai_para_o_openclaude(calls: dict[str, int]) -> None:
    prompt = await _prepare(False, [], openclaude=True)
    assert prompt is not None and prompt.startswith("/add /repos/x")
    assert calls["add"] == 1


def _patch_http(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    real_client = httpx.AsyncClient

    def factory(*_args, **kwargs):
        return real_client(transport=httpx.MockTransport(handler), timeout=kwargs.get("timeout"))

    monkeypatch.setattr(_resume.httpx, "AsyncClient", factory)


async def test_consulta_a_sessao_no_sandbox(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"exists": True})

    _patch_http(monkeypatch, handler)
    assert await _resume.claude_cli_session_exists("http://sb:8080", "u:c") is True
    assert seen[0].url.path == "/claude/sessions"
    assert seen[0].url.params["key"] == "u:c"


async def test_na_duvida_leva_o_contexto_completo(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_http(monkeypatch, lambda _r: httpx.Response(404, json={"error": "Not found"}))
    assert await _resume.claude_cli_session_exists("http://sb:8080", "u:c") is False

    def boom(_request):
        raise httpx.ConnectError("sandbox fora")

    _patch_http(monkeypatch, boom)
    assert await _resume.claude_cli_session_exists("http://sb:8080", "u:c") is False
    assert await _resume.claude_cli_session_exists("", "u:c") is False
