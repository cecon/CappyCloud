"""In-memory MCP repositories used by tests."""

from __future__ import annotations

import uuid

from app.domain.entities import McpServer, UserMcpServer
from app.ports.mcp_repository import McpServerRepository, UserMcpServerRepository


class InMemoryMcpRepository(McpServerRepository):
    """In-memory MCP store for testing (ADR-004 §6, por sandbox)."""

    def __init__(self) -> None:
        self._store: dict[uuid.UUID, McpServer] = {}

    async def list_for_sandbox(self, sandbox_id: uuid.UUID) -> list[McpServer]:
        rows = [m for m in self._store.values() if m.sandbox_id == sandbox_id]
        return sorted(rows, key=lambda m: m.created_at)

    async def get(self, mcp_id: uuid.UUID, sandbox_id: uuid.UUID) -> McpServer | None:
        mcp = self._store.get(mcp_id)
        if mcp is None or mcp.sandbox_id != sandbox_id:
            return None
        return mcp

    async def get_by_name(self, name: str, sandbox_id: uuid.UUID) -> McpServer | None:
        return next(
            (m for m in self._store.values() if m.sandbox_id == sandbox_id and m.name == name),
            None,
        )

    async def create(self, mcp: McpServer) -> McpServer:
        self._store[mcp.id] = mcp
        return mcp

    async def update(self, mcp: McpServer) -> McpServer:
        if mcp.id not in self._store:
            raise ValueError(f"McpServer {mcp.id} not found")
        self._store[mcp.id] = mcp
        return mcp

    async def delete(self, mcp_id: uuid.UUID, sandbox_id: uuid.UUID) -> bool:
        mcp = self._store.get(mcp_id)
        if mcp is None or mcp.sandbox_id != sandbox_id:
            return False
        del self._store[mcp_id]
        return True


class InMemoryUserMcpServerRepository(UserMcpServerRepository):
    def __init__(self) -> None:
        self._store: dict[uuid.UUID, UserMcpServer] = {}

    async def list_for_user(self, user_id: uuid.UUID) -> list[UserMcpServer]:
        rows = [server for server in self._store.values() if server.user_id == user_id]
        return sorted(rows, key=lambda server: server.created_at)

    async def get(self, server_id: uuid.UUID, user_id: uuid.UUID) -> UserMcpServer | None:
        server = self._store.get(server_id)
        if server is None or server.user_id != user_id:
            return None
        return server

    async def get_by_id(self, server_id: uuid.UUID) -> UserMcpServer | None:
        return self._store.get(server_id)

    async def get_by_name(self, name: str, user_id: uuid.UUID) -> UserMcpServer | None:
        return next(
            (
                server
                for server in self._store.values()
                if server.user_id == user_id and server.name == name
            ),
            None,
        )

    async def get_by_token_hash(self, token_hash: str) -> UserMcpServer | None:
        return next(
            (server for server in self._store.values() if server.token_hash == token_hash),
            None,
        )

    async def create(self, server: UserMcpServer) -> UserMcpServer:
        self._store[server.id] = server
        return server

    async def update(self, server: UserMcpServer) -> UserMcpServer:
        if server.id not in self._store:
            raise ValueError(f"UserMcpServer {server.id} not found")
        self._store[server.id] = server
        return server

    async def delete(self, server_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        server = self._store.get(server_id)
        if server is None or server.user_id != user_id:
            return False
        del self._store[server_id]
        return True

    async def touch_last_used(self, server_id: uuid.UUID) -> None:
        server = self._store.get(server_id)
        if server is not None:
            server.last_used_at = server.updated_at
