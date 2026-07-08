from __future__ import annotations

import uuid
from typing import Any

import pytest
from app.application.use_cases.repository_mcp import (
    HandleRepositoryMcpRequest,
    RepositoryMcpAuthError,
)
from app.application.use_cases.user_mcp_servers import hash_mcp_token
from app.domain.entities import UserMcpServer
from app.ports.mcp_telemetry import McpToolInvocationRecord
from app.ports.repository_mcp import RepositoryMcpToolGateway

from tests.conftest import InMemoryUserMcpServerRepository


class FakeToolGateway(RepositoryMcpToolGateway):
    async def call_tool(
        self,
        server: UserMcpServer,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        return {"tool": tool_name, "repository_id": str(server.repository_id), "args": arguments}


async def _server(repo: InMemoryUserMcpServerRepository, token: str) -> UserMcpServer:
    server = UserMcpServer(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        repository_id=uuid.uuid4(),
        name="Claude",
        token_hash=hash_mcp_token(token),
        token_preview=token[-8:],
    )
    return await repo.create(server)


class TestHandleRepositoryMcpRequest:
    async def test_initialize_lists_capabilities(self) -> None:
        repo = InMemoryUserMcpServerRepository()
        token = "cappy_mcp_test"
        server = await _server(repo, token)

        result = await HandleRepositoryMcpRequest(repo, FakeToolGateway()).execute(
            server_id=server.id,
            token=token,
            message={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        )

        assert result is not None
        assert result["result"]["protocolVersion"] == "2025-06-18"
        assert result["result"]["capabilities"] == {"tools": {"listChanged": False}}
        assert result["result"]["serverInfo"]["name"] == "SmartCodeBase"

    async def test_initialize_honours_supported_client_protocol(self) -> None:
        repo = InMemoryUserMcpServerRepository()
        token = "cappy_mcp_test"
        server = await _server(repo, token)

        result = await HandleRepositoryMcpRequest(repo, FakeToolGateway()).execute(
            server_id=server.id,
            token=token,
            message={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-03-26"},
            },
        )

        assert result is not None
        assert result["result"]["protocolVersion"] == "2025-03-26"

    async def test_tools_list_exposes_smart_codebase_aliases(self) -> None:
        repo = InMemoryUserMcpServerRepository()
        token = "cappy_mcp_test"
        server = await _server(repo, token)

        result = await HandleRepositoryMcpRequest(repo, FakeToolGateway()).execute(
            server_id=server.id,
            token=token,
            message={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        )

        assert result is not None
        names = {tool["name"] for tool in result["result"]["tools"]}
        assert "repository_search" in names
        assert "smart_codebase_search" in names
        assert all("graph" not in name for name in names)

    async def test_calls_known_tool_as_text_payload(self) -> None:
        repo = InMemoryUserMcpServerRepository()
        token = "cappy_mcp_test"
        server = await _server(repo, token)

        result = await HandleRepositoryMcpRequest(repo, FakeToolGateway()).execute(
            server_id=server.id,
            token=token,
            message={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "repository_search", "arguments": {"query": "needle"}},
            },
        )

        assert result is not None
        assert "repository_search" in result["result"]["content"][0]["text"]
        assert result["result"]["isError"] is False

    async def test_calls_smart_codebase_alias_as_canonical_tool(self) -> None:
        repo = InMemoryUserMcpServerRepository()
        token = "cappy_mcp_test"
        server = await _server(repo, token)

        result = await HandleRepositoryMcpRequest(repo, FakeToolGateway()).execute(
            server_id=server.id,
            token=token,
            message={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "smart_codebase_search", "arguments": {"query": "needle"}},
            },
        )

        assert result is not None
        assert "repository_search" in result["result"]["content"][0]["text"]

    async def test_rejects_wrong_token(self) -> None:
        repo = InMemoryUserMcpServerRepository()
        server = await _server(repo, "cappy_mcp_test")

        with pytest.raises(RepositoryMcpAuthError):
            await HandleRepositoryMcpRequest(repo, FakeToolGateway()).execute(
                server_id=server.id,
                token="wrong",
                message={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            )

    async def test_unknown_tool_returns_jsonrpc_error(self) -> None:
        repo = InMemoryUserMcpServerRepository()
        token = "cappy_mcp_test"
        server = await _server(repo, token)

        result = await HandleRepositoryMcpRequest(repo, FakeToolGateway()).execute(
            server_id=server.id,
            token=token,
            message={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "missing", "arguments": {}},
            },
        )

        assert result is not None
        assert result["error"]["code"] == -32601

    async def test_unknown_tool_records_telemetry_error(self) -> None:
        repo = InMemoryUserMcpServerRepository()
        token = "cappy_mcp_test"
        server = await _server(repo, token)
        rows: list[McpToolInvocationRecord] = []

        result = await HandleRepositoryMcpRequest(
            repo,
            FakeToolGateway(),
            rows.append,
        ).execute_for_server(
            server=server,
            message={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "missing", "arguments": {"token": "secret"}},
            },
            telemetry_context={
                "trace_id": uuid.uuid4(),
                "caller_user_agent": "Claude",
                "caller_session_id": "session",
            },
        )

        assert result is not None
        assert result["error"]["code"] == -32601
        assert len(rows) == 1
        assert rows[0].tool_name == "missing"
        assert rows[0].status == "error"
        assert rows[0].arguments_sanitized["token"] == "<redacted>"
