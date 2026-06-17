#!/usr/bin/env python3
"""Minimal Confluence MCP server over stdio.

Exposes read-only tools for Confluence pages using Atlassian REST APIs.
Configuration is provided by environment variables:

  CONFLUENCE_BASE_URL       e.g. https://company.atlassian.net/wiki
  CONFLUENCE_AUTHORIZATION  Full Authorization header value, if already issued
  CONFLUENCE_BASIC_TOKEN    Pre-encoded Basic auth token
  CONFLUENCE_EMAIL          Atlassian account email for API token auth
  CONFLUENCE_API_TOKEN      Atlassian API token
  CONFLUENCE_PAT            Optional bearer token/PAT alternative
  CONFLUENCE_MAIN_MENU_URL  Optional landing/menu page URL
"""

from __future__ import annotations

import json
import sys
import traceback
from typing import Any

from confluence_mcp_lib import (
    SERVER_NAME,
    SERVER_VERSION,
    confluence_get_main_menu,
    confluence_get_page,
    confluence_search,
)

_stdio_mode = "jsonl"


def _read_message() -> dict[str, Any] | None:
    global _stdio_mode
    headers: dict[str, str] = {}
    line = sys.stdin.buffer.readline()
    if line == b"":
        return None
    decoded = line.decode("utf-8", errors="replace").strip()
    if decoded and not decoded.lower().startswith("content-length:"):
        _stdio_mode = "jsonl"
        return json.loads(decoded)

    if decoded:
        key, _, value = decoded.partition(":")
        headers[key.lower()] = value.strip()
    _stdio_mode = "framed"

    while True:
        line = sys.stdin.buffer.readline()
        if line == b"":
            return None
        decoded = line.decode("utf-8", errors="replace").strip()
        if not decoded:
            break
        key, _, value = decoded.partition(":")
        headers[key.lower()] = value.strip()

    length = int(headers.get("content-length", "0") or "0")
    if length <= 0:
        return None
    raw = sys.stdin.buffer.read(length)
    return json.loads(raw.decode("utf-8"))


def _write_message(payload: dict[str, Any]) -> None:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if _stdio_mode == "jsonl":
        sys.stdout.buffer.write(raw + b"\n")
        sys.stdout.buffer.flush()
        return
    sys.stdout.buffer.write(f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii"))
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()


def _result(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


TOOLS = [
    {
        "name": "confluence_search",
        "description": (
            "Busca páginas no Confluence usando CQL text search. "
            "Use para localizar documentação interna antes de responder."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Termo de busca textual."},
                "space": {"type": "string", "description": "Space key opcional."},
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Rótulos opcionais; a busca retorna páginas com qualquer um deles."
                    ),
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "confluence_get_page",
        "description": (
            "Lê uma página do Confluence por page_id ou URL e retorna texto limpo com metadados."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string", "description": "ID numérico da página."},
                "url": {"type": "string", "description": "URL da página."},
            },
        },
    },
    {
        "name": "confluence_get_main_menu",
        "description": (
            "Lê a página principal/menu do Confluence configurada em CONFLUENCE_MAIN_MENU_URL."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
]

HANDLERS = {
    "confluence_search": confluence_search,
    "confluence_get_page": confluence_get_page,
    "confluence_get_main_menu": confluence_get_main_menu,
}


def _tool_response(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(data, ensure_ascii=False, indent=2),
            }
        ]
    }


def handle(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    if request_id is None:
        return None

    if method == "initialize":
        return _result(
            request_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        )
    if method == "tools/list":
        return _result(request_id, {"tools": TOOLS})
    if method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name not in HANDLERS:
            return _error(request_id, -32601, f"Tool desconhecida: {name}")
        try:
            return _result(request_id, _tool_response(HANDLERS[name](arguments)))
        except Exception as exc:
            return _result(
                request_id,
                {
                    "isError": True,
                    "content": [{"type": "text", "text": str(exc)}],
                },
            )
    return _error(request_id, -32601, f"Método não suportado: {method}")


def main() -> int:
    while True:
        try:
            message = _read_message()
            if message is None:
                return 0
            response = handle(message)
            if response is not None:
                _write_message(response)
        except Exception:
            traceback.print_exc(file=sys.stderr)
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
