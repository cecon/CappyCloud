"""Use cases — gerenciamento de servidores MCP por utilizador.

Operações:
  ListMcpServers    — lista todos os MCPs do utilizador
  CreateMcpServer   — cria novo MCP (valida nome único)
  UpdateMcpServer   — atualiza MCP existente
  DeleteMcpServer   — remove MCP
  ExportMcpConfig   — exporta no formato mcpServers do openclaude
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.domain.entities import McpServer
from app.ports.mcp_repository import McpServerRepository


class ListMcpServers:
    def __init__(self, repo: McpServerRepository) -> None:
        self._repo = repo

    async def execute(self, user_id: uuid.UUID) -> list[McpServer]:
        return await self._repo.list_for_user(user_id)


class CreateMcpServer:
    def __init__(self, repo: McpServerRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        user_id: uuid.UUID,
        name: str,
        command: str,
        args: list[str],
        env: dict[str, str],
        enabled: bool = True,
    ) -> McpServer:
        existing = await self._repo.get_by_name(name, user_id)
        if existing:
            raise ValueError(f"MCP '{name}' já existe para este utilizador.")

        mcp = McpServer(
            id=uuid.uuid4(),
            user_id=user_id,
            name=name,
            command=command,
            args=args,
            env=env,
            enabled=enabled,
        )
        return await self._repo.create(mcp)


class UpdateMcpServer:
    def __init__(self, repo: McpServerRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        mcp_id: uuid.UUID,
        user_id: uuid.UUID,
        name: str,
        command: str,
        args: list[str],
        env: dict[str, str],
        enabled: bool,
    ) -> McpServer:
        mcp = await self._repo.get(mcp_id, user_id)
        if not mcp:
            raise ValueError("MCP não encontrado.")

        # Se mudou o nome, verifica unicidade
        if mcp.name != name:
            existing = await self._repo.get_by_name(name, user_id)
            if existing:
                raise ValueError(f"MCP '{name}' já existe para este utilizador.")

        mcp.name = name
        mcp.command = command
        mcp.args = args
        mcp.env = env
        mcp.enabled = enabled
        mcp.updated_at = datetime.now(UTC)
        return await self._repo.update(mcp)


class DeleteMcpServer:
    def __init__(self, repo: McpServerRepository) -> None:
        self._repo = repo

    async def execute(self, mcp_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        return await self._repo.delete(mcp_id, user_id)


class ExportMcpConfig:
    """Exporta a configuração de MCPs no formato aceite pelo openclaude.

    Retorna um dict com a chave ``mcpServers`` pronto para serializar em
    ``~/.claude/settings.json``.
    """

    def __init__(self, repo: McpServerRepository) -> None:
        self._repo = repo

    async def execute(self, user_id: uuid.UUID) -> dict:
        servers = await self._repo.list_for_user(user_id)
        mcp_servers: dict[str, dict] = {}
        for s in servers:
            if not s.enabled:
                continue
            entry: dict = {"command": s.command}
            if s.args:
                entry["args"] = s.args
            if s.env:
                entry["env"] = s.env
            mcp_servers[s.name] = entry
        return {"mcpServers": mcp_servers}
