"""JSON-RPC MCP runtime for user repository endpoints."""

from __future__ import annotations

import json
import uuid
from contextlib import suppress
from typing import Any

from app.application.use_cases.mcp_telemetry import (
    TelemetryRecorder,
    call_tool_with_telemetry,
)
from app.application.use_cases.user_mcp_servers import hash_mcp_token
from app.domain.entities import UserMcpServer
from app.ports.mcp_repository import UserMcpServerRepository
from app.ports.repository_mcp import RepositoryMcpToolGateway

SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
DEFAULT_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[0]


class RepositoryMcpAuthError(Exception):
    """Invalid, disabled, or mismatched repository MCP token."""


def _result(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _tool_text(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "isError": False,
        "content": [
            {
                "type": "text",
                "text": json.dumps(data, ensure_ascii=False, indent=2),
            }
        ],
    }


CANONICAL_TOOLS: list[dict[str, Any]] = [
    {
        "name": "repository_list_files",
        "title": "SmartCodeBase: listar arquivos",
        "description": "SmartCodeBase: lista arquivos versionados do repositorio autorizado.",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "repository_read_file",
        "title": "SmartCodeBase: ler arquivo",
        "description": (
            "SmartCodeBase: le um arquivo por caminho relativo no repositorio autorizado."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "repository_search",
        "title": "SmartCodeBase: buscar texto",
        "description": "SmartCodeBase: busca texto fixo no codigo do repositorio usando ripgrep.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            "required": ["query"],
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "repository_grep",
        "title": "SmartCodeBase: grep regex",
        "description": "SmartCodeBase: busca por expressao regular no codigo usando ripgrep.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            "required": ["pattern"],
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "skills_search",
        "title": "SmartCodeBase: buscar skills",
        "description": (
            "SmartCodeBase: busca skills e documentos indexados do repositorio autorizado, "
            "incluindo Markdown, PDF, DOCX e planilhas importadas."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 10},
            },
            "required": ["query"],
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "confluence_search",
        "title": "SmartCodeBase: buscar Confluence",
        "description": "SmartCodeBase: busca documentacao Confluence configurada no repositorio.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "space": {"type": "string"},
                "labels": {"type": "array", "items": {"type": "string"}},
                "limit": {"type": "integer", "minimum": 1, "maximum": 10},
            },
            "required": ["query"],
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "confluence_get_page",
        "title": "SmartCodeBase: ler pagina Confluence",
        "description": "SmartCodeBase: le uma pagina Confluence por page_id ou URL.",
        "inputSchema": {
            "type": "object",
            "properties": {"page_id": {"type": "string"}, "url": {"type": "string"}},
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
]

SMART_CODEBASE_ALIASES = {
    "smart_codebase_list_files": "repository_list_files",
    "smart_codebase_read_file": "repository_read_file",
    "smart_codebase_search": "repository_search",
    "smart_codebase_grep": "repository_grep",
    "smart_codebase_search_skills": "skills_search",
    "smart_codebase_search_confluence": "confluence_search",
    "smart_codebase_get_confluence_page": "confluence_get_page",
}

TOOLS: list[dict[str, Any]] = [
    *CANONICAL_TOOLS,
    *[
        {
            **tool,
            "name": alias,
            "title": str(tool.get("title", "")).replace("SmartCodeBase:", "SmartCodeBase alias:"),
            "description": f"Alias SmartCodeBase para {canonical}. {tool['description']}",
        }
        for alias, canonical in SMART_CODEBASE_ALIASES.items()
        for tool in CANONICAL_TOOLS
        if tool["name"] == canonical
    ],
]

KNOWN_TOOL_NAMES = {tool["name"] for tool in TOOLS}


def _negotiate_protocol_version(message: dict[str, Any]) -> str:
    params = message.get("params") or {}
    if not isinstance(params, dict):
        return DEFAULT_PROTOCOL_VERSION
    requested = str(params.get("protocolVersion") or "")
    if requested in SUPPORTED_PROTOCOL_VERSIONS:
        return requested
    return DEFAULT_PROTOCOL_VERSION


class HandleRepositoryMcpRequest:
    def __init__(
        self,
        repo: UserMcpServerRepository,
        gateway: RepositoryMcpToolGateway,
        telemetry_recorder: TelemetryRecorder | None = None,
    ) -> None:
        self._repo = repo
        self._gateway = gateway
        self._telemetry_recorder = telemetry_recorder

    async def execute(
        self,
        *,
        server_id: uuid.UUID,
        token: str,
        message: dict[str, Any],
    ) -> dict[str, Any] | None:
        server = await self._repo.get_by_token_hash(hash_mcp_token(token))
        if server is None or server.id != server_id or not server.enabled:
            raise RepositoryMcpAuthError("Token MCP invalido ou servidor desativado.")
        return await self.execute_for_server(server=server, message=message)

    async def execute_for_server(
        self,
        *,
        server: UserMcpServer,
        message: dict[str, Any],
        telemetry_context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        await self._repo.touch_last_used(server.id)

        method = str(message.get("method") or "")
        request_id = message.get("id")
        if request_id is None:
            return None
        if method == "initialize":
            return _result(
                request_id,
                {
                    "protocolVersion": _negotiate_protocol_version(message),
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "SmartCodeBase", "version": "0.1.0"},
                    "instructions": (
                        "Use as tools SmartCodeBase para ler arquivos, buscar texto, executar "
                        "grep, encontrar skills, buscar documentos importados e pesquisar "
                        "Confluence do repositorio autorizado."
                    ),
                },
            )
        if method == "ping":
            return _result(request_id, {})
        if method == "tools/list":
            return _result(request_id, {"tools": TOOLS})
        if method == "tools/call":
            return await self._call_tool(request_id, server, message, telemetry_context)
        return _error(request_id, -32601, f"Metodo nao suportado: {method}")

    async def _call_tool(
        self,
        request_id: Any,
        server: Any,
        message: dict[str, Any],
        telemetry_context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        params = message.get("params") or {}
        if not isinstance(params, dict):
            return _error(request_id, -32602, "params invalido.")
        name = str(params.get("name") or "")
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            return _error(request_id, -32602, "arguments invalido.")
        canonical_name = SMART_CODEBASE_ALIASES.get(name, name)
        if name not in KNOWN_TOOL_NAMES or canonical_name not in KNOWN_TOOL_NAMES:
            if self._telemetry_recorder and telemetry_context:

                async def _unknown_tool() -> dict[str, Any]:
                    raise ValueError(f"Tool desconhecida: {name}")

                with suppress(ValueError):
                    await call_tool_with_telemetry(
                        server=server,
                        tool_name=name or "unknown",
                        arguments=arguments,
                        trace_id=telemetry_context["trace_id"],
                        caller_user_agent=telemetry_context.get("caller_user_agent"),
                        caller_session_id=telemetry_context.get("caller_session_id"),
                        metadata={"unknown_tool": True},
                        recorder=self._telemetry_recorder,
                        call=_unknown_tool,
                    )
            return _error(request_id, -32601, f"Tool desconhecida: {name}")
        metadata = {"requested_tool_name": name} if name != canonical_name else {}
        try:

            async def _call() -> dict[str, Any]:
                data = await self._gateway.call_tool(server, canonical_name, arguments)
                return _result(request_id, _tool_text(data))

            if self._telemetry_recorder and telemetry_context:
                return await call_tool_with_telemetry(
                    server=server,
                    tool_name=canonical_name,
                    arguments=arguments,
                    trace_id=telemetry_context["trace_id"],
                    caller_user_agent=telemetry_context.get("caller_user_agent"),
                    caller_session_id=telemetry_context.get("caller_session_id"),
                    metadata=metadata,
                    recorder=self._telemetry_recorder,
                    call=_call,
                )
            return await _call()
        except Exception as exc:
            return _result(
                request_id,
                {"isError": True, "content": [{"type": "text", "text": str(exc)}]},
            )
