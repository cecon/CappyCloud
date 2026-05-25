"""Client ID helpers for repository MCP OAuth flows."""

from __future__ import annotations

import uuid
from urllib.parse import urlsplit

STATIC_CLIENT_PREFIX = "cappy_mcp_client_"
CLAUDE_HOSTED_REDIRECT_URIS = {
    "https://claude.ai/api/mcp/auth_callback",
    "https://claude.ai/api/oauth/callback",
}


def static_mcp_client_id(server_id: uuid.UUID | str) -> str:
    return str(server_id)


def server_id_from_static_client_id(client_id: str) -> uuid.UUID | None:
    raw = (
        client_id.removeprefix(STATIC_CLIENT_PREFIX)
        if client_id.startswith(STATIC_CLIENT_PREFIX)
        else client_id
    )
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


def static_redirect_allowed(redirect_uri: str) -> bool:
    if redirect_uri in CLAUDE_HOSTED_REDIRECT_URIS:
        return True
    parsed = urlsplit(redirect_uri)
    return parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
