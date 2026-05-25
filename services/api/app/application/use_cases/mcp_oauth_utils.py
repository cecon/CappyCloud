"""Small OAuth helpers shared by MCP OAuth use cases."""

from __future__ import annotations

import base64
import hashlib
import re
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import quote, urlsplit, urlunsplit

from jose import JWTError, jwt

OAUTH_TOKEN_PREFIX = "cappy_oauth_"


class McpOAuthError(Exception):
    """OAuth request cannot be completed."""


class McpOAuthTokenCodec:
    def __init__(self, *, secret: str, algorithm: str) -> None:
        self._secret = secret
        self._algorithm = algorithm

    def encode(self, payload: dict, *, ttl_seconds: int) -> str:
        now = datetime.now(UTC)
        data = {**payload, "iat": now, "exp": now + timedelta(seconds=ttl_seconds)}
        return str(jwt.encode(data, self._secret, algorithm=self._algorithm))

    def encode_opaque(self, payload: dict, *, ttl_seconds: int) -> str:
        return wrap_opaque_oauth_token(self.encode(payload, ttl_seconds=ttl_seconds))

    def decode(self, token: str, *, expected_type: str) -> dict:
        token = unwrap_opaque_oauth_token(token)
        try:
            payload: dict = jwt.decode(
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


def unwrap_opaque_oauth_token(token: str) -> str:
    if not token.startswith(OAUTH_TOKEN_PREFIX):
        return token
    encoded = token.removeprefix(OAUTH_TOKEN_PREFIX)
    padded = f"{encoded}{'=' * (-len(encoded) % 4)}"
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii")).decode("ascii")
    except (ValueError, UnicodeDecodeError) as exc:
        raise McpOAuthError("Token OAuth inválido ou expirado.") from exc


def wrap_opaque_oauth_token(encoded_jwt: str) -> str:
    wrapped = base64.urlsafe_b64encode(encoded_jwt.encode("ascii")).decode("ascii").rstrip("=")
    return f"{OAUTH_TOKEN_PREFIX}{wrapped}"


def server_id_from_resource(resource: str) -> uuid.UUID | None:
    match = re.search(r"/api/mcp/servers/([0-9a-fA-F-]{36})(?:$|[/?#])", resource or "")
    if not match:
        return None
    try:
        return uuid.UUID(match.group(1))
    except ValueError:
        return None


def pkce_matches(verifier: str, challenge: str, method: str) -> bool:
    if not challenge:
        return True
    if not verifier:
        return False
    if method.upper() == "S256":
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        encoded = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return encoded == challenge
    return verifier == challenge


def urlquote(value: str) -> str:
    return quote(value, safe="")


def canonical_resource(resource: str) -> str:
    if not resource:
        return ""
    parsed = urlsplit(resource)
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()
    netloc = _canonical_netloc(scheme, hostname, parsed.port)
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((scheme, netloc, path, parsed.query, ""))


def issuer_from_resource(resource: str) -> str:
    parsed = urlsplit(resource)
    if not parsed.scheme or not parsed.hostname:
        return ""
    scheme = parsed.scheme.lower()
    netloc = _canonical_netloc(scheme, parsed.hostname.lower(), parsed.port)
    return urlunsplit((scheme, netloc, "", "", ""))


def _canonical_netloc(scheme: str, hostname: str, port: int | None) -> str:
    if port and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
        return f"{hostname}:{port}"
    return hostname
