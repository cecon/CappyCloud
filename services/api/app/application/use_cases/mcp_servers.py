"""Use cases — gestão administrativa de MCPs por sandbox (ADR-004 §6).

Operações são todas por sandbox (admin only). O caller é responsável por
verificar o papel (``require_role(ADMIN)``) na camada HTTP.

Operações:
  ListSandboxMcps   — lista todos os MCPs de uma sandbox
  CreateSandboxMcp  — cria novo MCP (valida nome único dentro da sandbox)
  UpdateSandboxMcp  — atualiza MCP existente
  DeleteSandboxMcp  — remove MCP
  ExportSandboxMcpConfig — exporta como JSON ``mcpServers`` do openclaude
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.domain.entities import McpServer
from app.ports.mcp_repository import McpServerRepository


class McpServerNotFoundError(Exception):
    """MCP solicitado não existe na sandbox."""


class McpServerNameTakenError(Exception):
    """Já existe MCP com este nome na sandbox."""


class ListSandboxMcps:
    def __init__(self, repo: McpServerRepository) -> None:
        self._repo = repo

    async def execute(self, sandbox_id: uuid.UUID) -> list[McpServer]:
        return await self._repo.list_for_sandbox(sandbox_id)


class CreateSandboxMcp:
    def __init__(self, repo: McpServerRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        *,
        sandbox_id: uuid.UUID,
        name: str,
        command: str,
        args: list[str],
        env: dict[str, str],
        enabled: bool = True,
    ) -> McpServer:
        normalised = name.strip()
        if not normalised:
            raise ValueError("Nome do MCP é obrigatório.")
        existing = await self._repo.get_by_name(normalised, sandbox_id)
        if existing:
            raise McpServerNameTakenError(f"MCP '{normalised}' já existe nesta sandbox.")

        mcp = McpServer(
            id=uuid.uuid4(),
            sandbox_id=sandbox_id,
            name=normalised,
            command=command,
            args=list(args),
            env=dict(env),
            enabled=enabled,
        )
        return await self._repo.create(mcp)


class UpdateSandboxMcp:
    def __init__(self, repo: McpServerRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        *,
        mcp_id: uuid.UUID,
        sandbox_id: uuid.UUID,
        name: str,
        command: str,
        args: list[str],
        env: dict[str, str],
        enabled: bool,
    ) -> McpServer:
        mcp = await self._repo.get(mcp_id, sandbox_id)
        if not mcp:
            raise McpServerNotFoundError(f"MCP {mcp_id} não encontrado.")

        normalised = name.strip()
        if not normalised:
            raise ValueError("Nome do MCP é obrigatório.")
        if mcp.name != normalised:
            existing = await self._repo.get_by_name(normalised, sandbox_id)
            if existing:
                raise McpServerNameTakenError(f"MCP '{normalised}' já existe nesta sandbox.")

        mcp.name = normalised
        mcp.command = command
        mcp.args = list(args)
        mcp.env = dict(env)
        mcp.enabled = enabled
        mcp.updated_at = datetime.now(UTC)
        return await self._repo.update(mcp)


class DeleteSandboxMcp:
    def __init__(self, repo: McpServerRepository) -> None:
        self._repo = repo

    async def execute(self, mcp_id: uuid.UUID, sandbox_id: uuid.UUID) -> bool:
        return await self._repo.delete(mcp_id, sandbox_id)


class ExportSandboxMcpConfig:
    """Serializa o cadastro de MCPs no formato aceite pelo openclaude
    (``{"mcpServers": {name: {command, args, env}}}``). MCPs ``enabled=False``
    são omitidos.

    Este é o JSON que o bootstrap (ADR-004 §5) escreve em
    ``~/.claude/settings.json`` dentro do container ao boot.
    """

    def __init__(self, repo: McpServerRepository) -> None:
        self._repo = repo

    async def execute(self, sandbox_id: uuid.UUID) -> dict:
        servers = await self._repo.list_for_sandbox(sandbox_id)
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
