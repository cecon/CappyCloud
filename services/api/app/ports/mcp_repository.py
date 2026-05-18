"""Port — McpServerRepository ABC (ADR-004 §6).

MCP é configuração por sandbox: gerido por ADMIN, materializado no
``~/.claude/settings.json`` de cada container ao boot.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.domain.entities import McpServer


class McpServerRepository(ABC):
    @abstractmethod
    async def list_for_sandbox(self, sandbox_id: uuid.UUID) -> list[McpServer]:
        """Devolve todos os MCPs da sandbox (ativos e inativos), ordem cronológica."""

    @abstractmethod
    async def get(self, mcp_id: uuid.UUID, sandbox_id: uuid.UUID) -> McpServer | None:
        """Devolve um MCP por id, verificando que pertence à sandbox."""

    @abstractmethod
    async def get_by_name(self, name: str, sandbox_id: uuid.UUID) -> McpServer | None:
        """Devolve um MCP pelo nome único dentro da sandbox."""

    @abstractmethod
    async def create(self, mcp: McpServer) -> McpServer:
        """Persiste um novo MCP e devolve a entidade com timestamps preenchidos."""

    @abstractmethod
    async def update(self, mcp: McpServer) -> McpServer:
        """Actualiza um MCP existente e devolve a entidade actualizada."""

    @abstractmethod
    async def delete(self, mcp_id: uuid.UUID, sandbox_id: uuid.UUID) -> bool:
        """Remove o MCP. Devolve True se apagou, False se não existia."""
