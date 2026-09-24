"""GC de sessões: a sessão expirada é apagada; com trabalho pendente, fica bloqueada.

Antes, ``destroy_session`` buscava a sessão com ``get()``, que ignora
exatamente as expiradas — o GC nunca apagava nada e o disco enchia.
"""

from __future__ import annotations

import json

import httpx
import pytest

from tests.unit.agent_runtime_test_loader import ROOT, load_agent_module

_store_mod = load_agent_module(
    "services.cappycloud_agent._session_store",
    ROOT / "services/cappycloud_agent/_session_store.py",
)
_env_mod = load_agent_module(
    "services.cappycloud_agent._environment_manager",
    ROOT / "services/cappycloud_agent/_environment_manager.py",
)
SandboxRecord = _store_mod.SandboxRecord

_REPOS = [{"slug": "seller", "alias": "seller", "branch_name": "cappy/seller/abc-seller"}]


class _FakeStore:
    def __init__(self, record) -> None:
        self.record = record
        self.deleted: list[tuple[str, str]] = []
        self.blocked: list[tuple[str, str, str]] = []

    async def get(self, user_id, chat_id):
        return None  # expirada: o cache "quente" já não a devolve

    async def get_any(self, user_id, chat_id):
        return self.record

    async def list_expired_sessions(self):
        return [{"user_id": self.record.user_id, "chat_id": self.record.chat_id}]

    async def delete(self, user_id, chat_id) -> None:
        self.deleted.append((user_id, chat_id))

    async def mark_cleanup_blocked(self, user_id, chat_id, note) -> None:
        self.blocked.append((user_id, chat_id, note))


def _record() -> SandboxRecord:
    return SandboxRecord(
        user_id="u1",
        chat_id="abc-def",
        grpc_host="sandbox",
        grpc_port=50051,
        session_root="/repos/sessions/abcdef",
        repos=_REPOS,
    )


@pytest.fixture
def sandbox_responses(monkeypatch):
    """Intercepta o httpx do EnvironmentManager e devolve a resposta configurada."""
    calls: list[httpx.Request] = []
    state = {"response": httpx.Response(200, json={"deleted": True})}

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return state["response"]

    real_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(_env_mod.httpx, "AsyncClient", client_factory)
    return calls, state


def _manager(store) -> object:
    return _env_mod.EnvironmentManager(
        session_store=store, sandbox_host="sandbox", sandbox_grpc_port=50051
    )


async def test_gc_apaga_sessao_expirada(sandbox_responses) -> None:
    calls, _ = sandbox_responses
    store = _FakeStore(_record())

    await _manager(store).gc_expired()

    assert store.deleted == [("u1", "abc-def")]
    assert calls[0].method == "DELETE"
    assert calls[0].url.params["session_root"] == "/repos/sessions/abcdef"
    assert json.loads(calls[0].url.params["repos"]) == _REPOS
    assert "force" not in calls[0].url.params


async def test_trabalho_nao_enviado_bloqueia_sem_apagar(sandbox_responses) -> None:
    _, state = sandbox_responses
    state["response"] = httpx.Response(
        409, json={"blocked": [{"alias": "seller", "reason": "1 commit(s) sem push"}]}
    )
    store = _FakeStore(_record())

    removed = await _manager(store).destroy_session("u1", "abc-def")

    assert removed is False
    assert store.deleted == []
    assert store.blocked == [("u1", "abc-def", "seller: 1 commit(s) sem push")]


async def test_erro_do_sandbox_mantem_registro(sandbox_responses) -> None:
    _, state = sandbox_responses
    state["response"] = httpx.Response(400, json={"error": "session_root must be inside"})
    store = _FakeStore(_record())

    assert await _manager(store).destroy_session("u1", "abc-def") is False
    assert store.deleted == []


def test_registro_do_postgres_decodifica_repos_em_texto() -> None:
    record = SandboxRecord.from_dict(
        {
            "user_id": "u1",
            "chat_id": "c1",
            "grpc_host": "sandbox",
            "grpc_port": 50051,
            "session_root": "/repos/sessions/c1",
            "repos": json.dumps(_REPOS),
        }
    )

    assert record.repos == _REPOS
    assert record.working_directory == "/repos/sessions/c1/seller"
