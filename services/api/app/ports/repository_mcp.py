"""Ports for the user-facing repository MCP runtime."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.domain.entities import UserMcpServer


class RepositoryMcpToolGateway(ABC):
    @abstractmethod
    async def call_tool(
        self,
        server: UserMcpServer,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute one read-only MCP tool inside the server repository scope."""
