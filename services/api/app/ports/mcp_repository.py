"""Port — McpServerRepository ABC (ADR-004 §6).

MCP é configuração por sandbox: gerido por ADMIN, materializado no
``~/.claude/settings.json`` de cada container ao boot.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.domain.entities import McpServer, UserMcpServer


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


class UserMcpServerRepository(ABC):
    @abstractmethod
    async def list_for_user(self, user_id: uuid.UUID) -> list[UserMcpServer]:
        """Lista MCPs HTTP criados pelo utilizador."""

    @abstractmethod
    async def get(self, server_id: uuid.UUID, user_id: uuid.UUID) -> UserMcpServer | None:
        """Retorna um MCP HTTP do utilizador, ou None."""

    @abstractmethod
    async def get_by_id(self, server_id: uuid.UUID) -> UserMcpServer | None:
        """Retorna um MCP HTTP pelo id, sem filtrar por utilizador."""

    @abstractmethod
    async def get_by_name(self, name: str, user_id: uuid.UUID) -> UserMcpServer | None:
        """Retorna um MCP HTTP pelo nome único do utilizador."""

    @abstractmethod
    async def get_by_token_hash(self, token_hash: str) -> UserMcpServer | None:
        """Retorna um MCP HTTP autenticável pelo hash do token."""

    @abstractmethod
    async def create(self, server: UserMcpServer) -> UserMcpServer:
        """Persiste novo MCP HTTP."""

    @abstractmethod
    async def update(self, server: UserMcpServer) -> UserMcpServer:
        """Atualiza MCP HTTP existente."""

    @abstractmethod
    async def delete(self, server_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Remove MCP HTTP do utilizador."""

    @abstractmethod
    async def touch_last_used(self, server_id: uuid.UUID) -> None:
        """Atualiza last_used_at depois de autenticação MCP bem sucedida."""
