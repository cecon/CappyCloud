from __future__ import annotations

import json

import httpx
import pytest
from app.adapters.secondary.sandbox_user_workspace_client import SandboxUserWorkspaceClient


@pytest.mark.asyncio
async def test_sandbox_gateway_maps_ensure_response(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[dict] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(
            200,
            json={
                "workspace_path": "/repos/users/u/default/repo/main",
                "status": "ready",
                "action": "repaired",
                "dirty": False,
                "message": "dirty baseline repaired",
            },
        )

    transport = httpx.MockTransport(handler)

    class FakeAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            super().__init__(transport=transport)

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    client = SandboxUserWorkspaceClient("http://sandbox")

    result = await client.ensure_user_workspace(
        slug="repo",
        base_branch="main",
        workspace_path="/repos/users/u/default/repo/main",
        clone_url="https://github.com/acme/repo.git",
    )

    assert requests[0]["workspace_path"] == "/repos/users/u/default/repo/main"
    assert result.status == "ready"
    assert result.action == "repaired"
    assert result.message == "dirty baseline repaired"


@pytest.mark.asyncio
async def test_sandbox_gateway_maps_delete_response(monkeypatch: pytest.MonkeyPatch) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["workspace_path"] == "/repos/users/u/default/repo/main"
        return httpx.Response(200, json={"deleted": True})

    transport = httpx.MockTransport(handler)

    class FakeAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            super().__init__(transport=transport)

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    client = SandboxUserWorkspaceClient("http://sandbox")

    result = await client.delete_user_workspace(
        workspace_path="/repos/users/u/default/repo/main"
    )

    assert result.deleted is True
