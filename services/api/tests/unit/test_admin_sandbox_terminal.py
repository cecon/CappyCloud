"""Terminal web da sandbox: só super admin, repasse ao session server."""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import httpx
import pytest
from app.adapters.primary.http import admin_sandbox_terminal as terminal
from app.adapters.primary.http.admin_sandboxes import get_sandbox_repo
from app.adapters.primary.http.deps_auth import get_authenticated_user
from app.domain.entities import UserRole
from fastapi import FastAPI
from fastapi.testclient import TestClient

SANDBOX_ID = uuid.uuid4()
TERMINAL_ID = "a" * 32


class _Repo:
    async def get(self, sandbox_id):
        if sandbox_id != SANDBOX_ID:
            return None
        return SimpleNamespace(id=SANDBOX_ID, name="sb", host="sandbox", session_port=8080)


def _client(monkeypatch: pytest.MonkeyPatch, *, super_admin: bool, handler=None) -> TestClient:
    seen: list[httpx.Request] = []
    real_client = httpx.AsyncClient

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request) if handler else httpx.Response(200, json={"ok": True})

    def factory(*_args, **kwargs):
        return real_client(transport=httpx.MockTransport(record), timeout=kwargs.get("timeout"))

    monkeypatch.setattr(terminal.httpx, "AsyncClient", factory)
    monkeypatch.setenv("INTERNAL_API_TOKEN", "tok")
    app = FastAPI()
    app.include_router(terminal.router, prefix="/api")
    user = SimpleNamespace(
        id=uuid.uuid4(), email="eu@x.com", role=UserRole.ADMIN, is_super_admin=super_admin
    )
    app.dependency_overrides[get_authenticated_user] = lambda: user
    app.dependency_overrides[get_sandbox_repo] = lambda: _Repo()
    client = TestClient(app)
    client.seen = seen  # type: ignore[attr-defined]
    return client


def test_admin_comum_nao_abre_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch, super_admin=False)
    resp = client.post(f"/api/admin/sandboxes/{SANDBOX_ID}/terminal", json={})
    assert resp.status_code == 403
    assert client.seen == []  # type: ignore[attr-defined]


def test_abre_terminal_com_token_interno(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(
        monkeypatch,
        super_admin=True,
        handler=lambda _r: httpx.Response(200, json={"id": TERMINAL_ID}),
    )
    resp = client.post(f"/api/admin/sandboxes/{SANDBOX_ID}/terminal", json={"cols": 90, "rows": 25})
    assert resp.json() == {"id": TERMINAL_ID}
    request = client.seen[0]  # type: ignore[attr-defined]
    assert str(request.url) == "http://sandbox:8080/terminal/sessions"
    assert request.headers["X-Internal-Token"] == "tok"
    assert json.loads(request.content) == {"cols": 90, "rows": 25}


def test_entrada_redimensionamento_e_fechamento(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch, super_admin=True)
    base = f"/api/admin/sandboxes/{SANDBOX_ID}/terminal/{TERMINAL_ID}"
    assert client.post(f"{base}/input", json={"data": "claude login\r"}).status_code == 200
    assert client.post(f"{base}/resize", json={"cols": 100, "rows": 30}).status_code == 200
    assert client.delete(base).status_code == 200
    calls = [(r.method, r.url.path) for r in client.seen]  # type: ignore[attr-defined]
    assert calls == [
        ("POST", f"/terminal/sessions/{TERMINAL_ID}/input"),
        ("POST", f"/terminal/sessions/{TERMINAL_ID}/resize"),
        ("DELETE", f"/terminal/sessions/{TERMINAL_ID}"),
    ]


def test_stream_repassa_a_saida(monkeypatch: pytest.MonkeyPatch) -> None:
    lines = b'{"type": "output", "data": "b2k="}\n{"type": "exit", "code": 0}\n'
    client = _client(
        monkeypatch, super_admin=True, handler=lambda _r: httpx.Response(200, content=lines)
    )
    resp = client.get(f"/api/admin/sandboxes/{SANDBOX_ID}/terminal/{TERMINAL_ID}/stream")
    assert resp.headers["content-type"].startswith("application/x-ndjson")
    assert resp.content == lines


def test_erros_viram_mensagens_claras(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(
        monkeypatch,
        super_admin=True,
        handler=lambda _r: httpx.Response(404, json={"error": "Not found"}),
    )
    resp = client.post(f"/api/admin/sandboxes/{SANDBOX_ID}/terminal", json={})
    assert resp.status_code == 404
    assert "atualize a sandbox" in resp.json()["detail"]
    bad_id = client.post(f"/api/admin/sandboxes/{SANDBOX_ID}/terminal/../input", json={"data": ""})
    assert bad_id.status_code == 404
    assert client.post(f"/api/admin/sandboxes/{uuid.uuid4()}/terminal", json={}).status_code == 404
