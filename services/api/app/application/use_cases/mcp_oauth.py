"""OAuth helpers for Claude remote MCP connectors."""

from __future__ import annotations

import base64
import hashlib
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from jose import JWTError, jwt

from app.application.use_cases.mcp_oauth_clients import (
    server_id_from_static_client_id,
    static_redirect_allowed,
)
from app.application.use_cases.user_mcp_servers import hash_mcp_token
from app.domain.entities import UserMcpServer
from app.ports.mcp_repository import UserMcpServerRepository

CLIENT_TTL_SECONDS = 24 * 60 * 60
CODE_TTL_SECONDS = 5 * 60
ACCESS_TTL_SECONDS = 60 * 60
REFRESH_TTL_SECONDS = 30 * 24 * 60 * 60
OAUTH_SCOPE = "repository:read"
DEFAULT_TOKEN_ENDPOINT_AUTH_METHOD = "none"
SUPPORTED_TOKEN_ENDPOINT_AUTH_METHODS = ("none", "client_secret_basic", "client_secret_post")
OAUTH_TOKEN_PREFIX = "cappy_oauth_"


class McpOAuthError(Exception):
    """OAuth request cannot be completed."""


class McpOAuthService:
    def __init__(
        self,
        repo: UserMcpServerRepository,
        *,
        secret: str,
        algorithm: str,
    ) -> None:
        self._repo = repo
        self._secret = secret
        self._algorithm = algorithm

    def register_client(
        self,
        *,
        redirect_uris: list[str],
        client_name: str = "Claude",
        token_endpoint_auth_method: str = DEFAULT_TOKEN_ENDPOINT_AUTH_METHOD,
    ) -> dict[str, Any]:
        if not redirect_uris:
            raise McpOAuthError("redirect_uris é obrigatório.")
        if token_endpoint_auth_method not in SUPPORTED_TOKEN_ENDPOINT_AUTH_METHODS:
            raise McpOAuthError("token_endpoint_auth_method inválido.")
        client_secret = secrets.token_urlsafe(32)
        client_id = self._encode(
            {
                "typ": "mcp_oauth_client",
                "redirect_uris": redirect_uris,
                "client_name": client_name[:120],
                "token_endpoint_auth_method": token_endpoint_auth_method,
                "client_secret_hash": hash_mcp_token(client_secret),
            },
            ttl_seconds=CLIENT_TTL_SECONDS,
        )
        response: dict[str, Any] = {
            "client_id": client_id,
            "client_name": client_name,
            "redirect_uris": redirect_uris,
            "grant_types": ["authorization_code"],
            "response_types": ["code"],
            "token_endpoint_auth_method": token_endpoint_auth_method,
            "scope": OAUTH_SCOPE,
            "client_id_issued_at": int(datetime.now(UTC).timestamp()),
        }
        if token_endpoint_auth_method != "none":
            response["client_secret"] = client_secret
            response["client_secret_expires_at"] = 0
        return response

    async def authorize(
        self,
        *,
        response_type: str,
        client_id: str,
        redirect_uri: str,
        state: str,
        resource: str,
        default_resource_origin: str = "",
        code_challenge: str,
        code_challenge_method: str,
        mcp_token: str,
    ) -> str:
        if response_type != "code":
            raise McpOAuthError("response_type inválido.")
        self._validate_client_redirect(client_id, redirect_uri)
        server = await self._server_for_authorization(client_id, mcp_token)
        resolved_resource = resource.strip()
        if not resolved_resource and default_resource_origin:
            resolved_resource = f"{default_resource_origin.rstrip('/')}/api/mcp/servers/{server.id}"
        resource_server_id = server_id_from_resource(resolved_resource)
        if resource_server_id is not None and resource_server_id != server.id:
            raise McpOAuthError("Token MCP não pertence ao endpoint informado.")
        resolved_resource = _canonical_resource(resolved_resource)
        code = self._encode(
            {
                "typ": "mcp_oauth_code",
                "sid": str(server.id),
                "uid": str(server.user_id),
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "code_challenge": code_challenge,
                "code_challenge_method": code_challenge_method or "plain",
                "resource": resolved_resource,
            },
            ttl_seconds=CODE_TTL_SECONDS,
        )
        sep = "&" if "?" in redirect_uri else "?"
        state_part = f"&state={_urlquote(state)}" if state else ""
        return f"{redirect_uri}{sep}code={_urlquote(code)}{state_part}"

    async def exchange_code(
        self,
        *,
        grant_type: str,
        code: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        resource: str = "",
        code_verifier: str,
    ) -> dict[str, Any]:
        if grant_type != "authorization_code":
            raise McpOAuthError("grant_type inválido.")
        await self._validate_client_auth(client_id, client_secret)
        payload = self._decode(code, expected_type="mcp_oauth_code")
        if payload.get("client_id") != client_id or payload.get("redirect_uri") != redirect_uri:
            raise McpOAuthError("authorization code não pertence a este cliente.")
        if not _pkce_matches(
            code_verifier,
            str(payload.get("code_challenge") or ""),
            str(payload.get("code_challenge_method") or "plain"),
        ):
            raise McpOAuthError("PKCE inválido.")
        code_resource = _canonical_resource(str(payload.get("resource") or ""))
        requested_resource = _canonical_resource(resource)
        if code_resource and requested_resource and code_resource != requested_resource:
            raise McpOAuthError("resource não pertence ao authorization code.")
        resource = requested_resource or code_resource
        server_id = uuid.UUID(str(payload["sid"]))
        server = await self._repo.get_by_id(server_id)
        if server is None or not server.enabled:
            raise McpOAuthError("MCP server desativado ou inexistente.")
        access_token, refresh_token = self._issue_tokens(
            server=server,
            client_id=client_id,
            resource=resource,
        )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": ACCESS_TTL_SECONDS,
            "scope": OAUTH_SCOPE,
            "resource": resource,
        }

    async def refresh_access_token(
        self,
        *,
        grant_type: str,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ) -> dict[str, Any]:
        if grant_type != "refresh_token":
            raise McpOAuthError("grant_type inválido.")
        await self._validate_client_auth(client_id, client_secret)
        payload = self._decode(refresh_token, expected_type="mcp_oauth_refresh")
        if client_id and payload.get("client_id") != client_id:
            raise McpOAuthError("refresh token não pertence a este cliente.")
        resource = _canonical_resource(str(payload.get("resource") or payload.get("aud") or ""))
        server = await self._repo.get_by_id(uuid.UUID(str(payload["sid"])))
        if server is None or not server.enabled:
            raise McpOAuthError("MCP server desativado ou inexistente.")
        next_access_token, next_refresh_token = self._issue_tokens(
            server=server,
            client_id=str(payload.get("client_id") or client_id),
            resource=resource,
        )
        return {
            "access_token": next_access_token,
            "refresh_token": next_refresh_token,
            "token_type": "Bearer",
            "expires_in": ACCESS_TTL_SECONDS,
            "scope": OAUTH_SCOPE,
            "resource": resource,
        }

    async def resolve_bearer_token(
        self,
        *,
        server_id: uuid.UUID,
        token: str,
    ) -> UserMcpServer:
        if token.startswith("cappy_mcp_"):
            server = await self._server_from_mcp_token(token)
        else:
            payload = self._decode(token, expected_type="mcp_oauth_access")
            resolved = await self._repo.get_by_id(uuid.UUID(str(payload["sid"])))
            if resolved is None or not resolved.enabled:
                raise McpOAuthError("MCP server desativado ou inexistente.")
            server = resolved
        if server.id != server_id:
            raise McpOAuthError("Token MCP não pertence a este endpoint.")
        return server

    async def _server_from_mcp_token(self, token: str) -> UserMcpServer:
        server = await self._repo.get_by_token_hash(hash_mcp_token(token))
        if server is None or not server.enabled:
            raise McpOAuthError("Token MCP inválido ou servidor desativado.")
        return server

    async def _server_for_authorization(self, client_id: str, mcp_token: str) -> UserMcpServer:
        static_server_id = server_id_from_static_client_id(client_id)
        if static_server_id is None:
            return await self._server_from_mcp_token(mcp_token)
        server = await self._repo.get_by_id(static_server_id)
        if server is None or not server.enabled:
            raise McpOAuthError("MCP server desativado ou inexistente.")
        if mcp_token:
            token_server = await self._server_from_mcp_token(mcp_token)
            if token_server.id != server.id:
                raise McpOAuthError("Token MCP não pertence ao client_id informado.")
        return server

    def _issue_tokens(
        self,
        *,
        server: UserMcpServer,
        client_id: str,
        resource: str,
    ) -> tuple[str, str]:
        base = {
            "sub": str(server.id),
            "sid": str(server.id),
            "uid": str(server.user_id),
            "client_id": client_id,
            "iss": _issuer_from_resource(resource),
            "aud": resource,
            "resource": resource,
            "scope": OAUTH_SCOPE,
        }
        access_token = self._encode_opaque_oauth_token(
            {"typ": "mcp_oauth_access", "jti": secrets.token_urlsafe(16), **base},
            ttl_seconds=ACCESS_TTL_SECONDS,
        )
        refresh_token = self._encode_opaque_oauth_token(
            {"typ": "mcp_oauth_refresh", "jti": secrets.token_urlsafe(16), **base},
            ttl_seconds=REFRESH_TTL_SECONDS,
        )
        return access_token, refresh_token

    def _validate_client_redirect(self, client_id: str, redirect_uri: str) -> None:
        if server_id_from_static_client_id(client_id) is not None:
            if not static_redirect_allowed(redirect_uri):
                raise McpOAuthError("redirect_uri não permitida para este client_id.")
            return
        payload = self._decode(client_id, expected_type="mcp_oauth_client")
        redirect_uris = payload.get("redirect_uris")
        if not isinstance(redirect_uris, list) or redirect_uri not in redirect_uris:
            raise McpOAuthError("redirect_uri não registrada para este client_id.")

    async def _validate_client_auth(self, client_id: str, client_secret: str) -> None:
        static_server_id = server_id_from_static_client_id(client_id)
        if static_server_id is not None:
            server = await self._repo.get_by_id(static_server_id)
            if server is None or not server.enabled:
                raise McpOAuthError("MCP server desativado ou inexistente.")
            if not client_secret or hash_mcp_token(client_secret) != server.token_hash:
                raise McpOAuthError("client_secret inválido.")
            return
        payload = self._decode(client_id, expected_type="mcp_oauth_client")
        method = str(payload.get("token_endpoint_auth_method") or "none")
        if method == "none":
            return
        secret_hash = str(payload.get("client_secret_hash") or "")
        if not client_secret or hash_mcp_token(client_secret) != secret_hash:
            raise McpOAuthError("client_secret inválido.")

    def _encode(self, payload: dict[str, Any], *, ttl_seconds: int) -> str:
        now = datetime.now(UTC)
        data = {**payload, "iat": now, "exp": now + timedelta(seconds=ttl_seconds)}
        return str(jwt.encode(data, self._secret, algorithm=self._algorithm))

    def _encode_opaque_oauth_token(self, payload: dict[str, Any], *, ttl_seconds: int) -> str:
        encoded = self._encode(payload, ttl_seconds=ttl_seconds)
        wrapped = base64.urlsafe_b64encode(encoded.encode("ascii")).decode("ascii").rstrip("=")
        return f"{OAUTH_TOKEN_PREFIX}{wrapped}"

    def _decode(self, token: str, *, expected_type: str) -> dict[str, Any]:
        token = _unwrap_opaque_oauth_token(token)
        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                options={"verify_aud": False},
            )
        except JWTError as exc:
            raise McpOAuthError("Token OAuth inválido ou expirado.") from exc
        if payload.get("typ") != expected_type:
            raise McpOAuthError("Token OAuth com finalidade inválida.")
        return payload


def _unwrap_opaque_oauth_token(token: str) -> str:
    if not token.startswith(OAUTH_TOKEN_PREFIX):
        return token
    encoded = token.removeprefix(OAUTH_TOKEN_PREFIX)
    padded = f"{encoded}{'=' * (-len(encoded) % 4)}"
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii")).decode("ascii")
    except (ValueError, UnicodeDecodeError) as exc:
        raise McpOAuthError("Token OAuth inválido ou expirado.") from exc


def server_id_from_resource(resource: str) -> uuid.UUID | None:
    match = re.search(r"/api/mcp/servers/([0-9a-fA-F-]{36})(?:$|[/?#])", resource or "")
    if not match:
        return None
    try:
        return uuid.UUID(match.group(1))
    except ValueError:
        return None


def _pkce_matches(verifier: str, challenge: str, method: str) -> bool:
    if not challenge:
        return True
    if not verifier:
        return False
    if method.upper() == "S256":
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        encoded = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return encoded == challenge
    return verifier == challenge


def _urlquote(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="")


def _canonical_resource(resource: str) -> str:
    if not resource:
        return ""
    parsed = urlsplit(resource)
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()
    port = parsed.port
    netloc = hostname
    if port and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
        netloc = f"{netloc}:{port}"
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((scheme, netloc, path, parsed.query, ""))


def _issuer_from_resource(resource: str) -> str:
    parsed = urlsplit(resource)
    if not parsed.scheme or not parsed.hostname:
        return ""
    scheme = parsed.scheme.lower()
    hostname = parsed.hostname.lower()
    port = parsed.port
    netloc = hostname
    if port and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
        netloc = f"{netloc}:{port}"
    return urlunsplit((scheme, netloc, "", "", ""))
