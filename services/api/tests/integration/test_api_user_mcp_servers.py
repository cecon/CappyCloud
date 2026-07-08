from __future__ import annotations

import logging
import uuid

from app.adapters.primary.http.repository_mcp import get_mcp_telemetry_recorder
from app.domain.entities import Repository
from app.main import app
from app.ports.mcp_telemetry import McpToolInvocationRecord
from httpx import AsyncClient

from tests.conftest import (
    InMemoryRepositoryRepository,
    InMemoryUserRepositoryAccessRepository,
)


def _repository() -> Repository:
    return Repository(
        id=uuid.uuid4(),
        slug="demo",
        name="Demo",
        clone_url="https://github.com/acme/demo.git",
    )


class TestUserMcpServersApi:
    async def test_user_crud_and_runtime_endpoint(
        self,
        client: AsyncClient,
        user_headers: dict[str, str],
        repository_repo: InMemoryRepositoryRepository,
        repository_access_repo: InMemoryUserRepositoryAccessRepository,
    ) -> None:
        me = await client.get("/api/auth/me", headers=user_headers)
        user_id = uuid.UUID(me.json()["id"])
        repository = _repository()
        repository_repo.add(repository)
        await repository_access_repo.grant(user_id, repository.id)

        created = await client.post(
            "/api/mcp-servers",
            json={"name": "Claude Demo", "repository_id": str(repository.id), "enabled": True},
            headers=user_headers,
        )

        assert created.status_code == 201
        body = created.json()
        token = body["token"]
        server_id = body["id"]
        assert token.startswith("cappy_mcp_")
        assert body["token_preview"] == token[-8:]

        listed = await client.get("/api/mcp-servers", headers=user_headers)
        assert listed.status_code == 200
        assert "token" not in listed.json()[0]

        init = await client.post(
            f"/api/mcp/servers/{server_id}",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert init.status_code == 200
        assert init.json()["result"]["capabilities"] == {"tools": {"listChanged": False}}

        initialized = await client.post(
            f"/api/mcp/servers/{server_id}",
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert initialized.status_code == 202
        assert initialized.content == b""

        tool_call = await client.post(
            f"/api/mcp/servers/{server_id}",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "repository_search", "arguments": {"query": "foo"}},
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert tool_call.status_code == 200
        assert "repository_search" in tool_call.json()["result"]["content"][0]["text"]

        query_token_call = await client.post(
            f"/api/mcp/servers/{server_id}?mcp_token={token}",
            json={"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
        )
        assert query_token_call.status_code == 200
        tokenized_call = await client.post(
            f"/api/mcp/token/{token}/servers/{server_id}",
            json={"jsonrpc": "2.0", "id": 4, "method": "tools/list"},
        )
        assert tokenized_call.status_code == 200
        tokenized_metadata = await client.get(
            f"/.well-known/oauth-protected-resource/api/mcp/token/{token}/servers/{server_id}"
        )
        assert tokenized_metadata.status_code == 404

    async def test_runtime_records_mcp_tool_telemetry_and_echoes_trace(
        self,
        client: AsyncClient,
        user_headers: dict[str, str],
        repository_repo: InMemoryRepositoryRepository,
        repository_access_repo: InMemoryUserRepositoryAccessRepository,
    ) -> None:
        captured: list[McpToolInvocationRecord] = []
        app.dependency_overrides[get_mcp_telemetry_recorder] = lambda: captured.append
        me = await client.get("/api/auth/me", headers=user_headers)
        user_id = uuid.UUID(me.json()["id"])
        repository = _repository()
        repository_repo.add(repository)
        await repository_access_repo.grant(user_id, repository.id)
        created = await client.post(
            "/api/mcp-servers",
            json={"name": "Claude Telemetry", "repository_id": str(repository.id)},
            headers=user_headers,
        )
        trace_id = uuid.uuid4()

        tool_call = await client.post(
            f"/api/mcp/servers/{created.json()['id']}",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "smart_codebase_search",
                    "arguments": {"query": "foo", "apiKey": "secret"},
                },
            },
            headers={
                "Authorization": f"Bearer {created.json()['token']}",
                "X-Request-Id": str(trace_id),
                "Mcp-Session-Id": "claude-session",
                "User-Agent": "Claude",
            },
        )

        assert tool_call.status_code == 200
        assert tool_call.headers["x-request-id"] == str(trace_id)
        assert len(captured) == 1
        row = captured[0]
        assert row.trace_id == trace_id
        assert row.user_id == user_id
        assert row.repo_id == repository.id
        assert row.tool_name == "repository_search"
        assert row.caller_user_agent == "Claude"
        assert row.caller_session_id == "claude-session"
        assert row.arguments_sanitized["apiKey"] == "<redacted>"
        assert row.metadata["requested_tool_name"] == "smart_codebase_search"

    async def test_logs_unmapped_mcp_routes_without_token_values(
        self,
        client: AsyncClient,
        caplog,
    ) -> None:
        with caplog.at_level(logging.INFO, logger="app.main"):
            response = await client.get(
                "/api/mcp/token/cappy_mcp_secret-value/servers/not-found?mcp_token=secret",
                headers={"User-Agent": "python-httpx/0.28.1"},
            )

        app_logs = "\n".join(
            record.getMessage() for record in caplog.records if record.name == "app.main"
        )
        assert response.status_code in {404, 405}
        assert "MCP route miss" in app_logs
        assert "cappy_mcp_***" in app_logs
        assert "secret-value" not in app_logs
        assert "query_keys=mcp_token" in app_logs

    async def test_runtime_rejects_wrong_token(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        repository_repo: InMemoryRepositoryRepository,
    ) -> None:
        repository = _repository()
        repository_repo.add(repository)
        created = await client.post(
            "/api/mcp-servers",
            json={"name": "Admin MCP", "repository_id": str(repository.id), "enabled": True},
            headers=admin_headers,
        )
        server_id = created.json()["id"]

        response = await client.post(
            f"/api/mcp/servers/{server_id}",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"Authorization": "Bearer wrong"},
        )

        assert response.status_code == 401

    async def test_runtime_rejects_invalid_json_without_500(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        repository_repo: InMemoryRepositoryRepository,
    ) -> None:
        repository = _repository()
        repository_repo.add(repository)
        created = await client.post(
            "/api/mcp-servers",
            json={"name": "Invalid JSON MCP", "repository_id": str(repository.id), "enabled": True},
            headers=admin_headers,
        )
        token = created.json()["token"]
        server_id = created.json()["id"]

        response = await client.post(
            f"/api/mcp/servers/{server_id}",
            content="{bad",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )

        assert response.status_code == 400
