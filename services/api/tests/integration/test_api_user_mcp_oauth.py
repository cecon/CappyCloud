from __future__ import annotations

import base64
import hashlib
import uuid
from urllib.parse import parse_qs, urlparse

from app.application.use_cases.mcp_oauth import OAUTH_TOKEN_PREFIX
from app.application.use_cases.mcp_oauth_clients import static_mcp_client_id
from app.domain.entities import Repository
from app.infrastructure.config import get_settings
from httpx import AsyncClient
from jose import jwt

from tests.conftest import (
    InMemoryRepositoryRepository,
    InMemoryUserRepositoryAccessRepository,
)


def _repository() -> Repository:
    return Repository(
        id=uuid.uuid4(),
        slug="demo",
        name="Demo",
        clone_url="https://github.com/acme/demo.git",
    )


async def test_runtime_supports_claude_oauth_flow(
    client: AsyncClient,
    user_headers: dict[str, str],
    repository_repo: InMemoryRepositoryRepository,
    repository_access_repo: InMemoryUserRepositoryAccessRepository,
) -> None:
    user_id = uuid.UUID((await client.get("/api/auth/me", headers=user_headers)).json()["id"])
    repository = _repository()
    repository_repo.add(repository)
    await repository_access_repo.grant(user_id, repository.id)
    created = await client.post(
        "/api/mcp-servers",
        json={"name": "Claude OAuth", "repository_id": str(repository.id), "enabled": True},
        headers=user_headers,
    )
    server_id = created.json()["id"]
    endpoint = f"http://test/api/mcp/servers/{server_id}"
    challenge, verifier = _pkce_pair()
    registration = await client.post(
        "/api/mcp/oauth/register",
        json={"client_name": "Claude", "redirect_uris": ["https://claude.ai/api/oauth/callback"]},
    )
    client_id = registration.json()["client_id"]

    await _assert_oauth_metadata(client, server_id, endpoint, registration)
    authorized = await _authorize_dynamic_client(
        client, client_id, created.json()["token"], challenge
    )
    exchanged = await client.post(
        "/api/mcp/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": parse_qs(urlparse(authorized.headers["location"]).query)["code"][0],
            "client_id": client_id,
            "redirect_uri": "https://claude.ai/api/oauth/callback",
            "code_verifier": verifier,
        },
    )

    assert exchanged.status_code == 200
    assert set(exchanged.json()) == {"access_token", "token_type", "expires_in", "scope"}
    access_token = exchanged.json()["access_token"]
    assert access_token.startswith(OAUTH_TOKEN_PREFIX)
    payload = jwt.decode(
        _unwrap_opaque_test_token(access_token),
        get_settings().jwt_secret,
        algorithms=[get_settings().jwt_algorithm],
        options={"verify_aud": False},
    )
    assert payload["iss"] == "http://test"
    assert payload["aud"] == endpoint
    await _assert_token_allows_tool_list(client, server_id, access_token)


async def test_runtime_supports_static_claude_client_credentials(
    client: AsyncClient,
    user_headers: dict[str, str],
    repository_repo: InMemoryRepositoryRepository,
    repository_access_repo: InMemoryUserRepositoryAccessRepository,
) -> None:
    user_id = uuid.UUID((await client.get("/api/auth/me", headers=user_headers)).json()["id"])
    repository = _repository()
    repository_repo.add(repository)
    await repository_access_repo.grant(user_id, repository.id)
    created = await client.post(
        "/api/mcp-servers",
        json={"name": "Claude Static", "repository_id": str(repository.id), "enabled": True},
        headers=user_headers,
    )
    server_id = uuid.UUID(created.json()["id"])
    endpoint = f"http://test/api/mcp/servers/{server_id}"
    client_id = static_mcp_client_id(server_id)
    challenge, verifier = _pkce_pair()

    code = await _authorize_static_client(client, client_id, endpoint, challenge)
    rejected = await _exchange_static_client(client, client_id, "wrong", code, verifier, endpoint)
    assert rejected.status_code == 400

    exchanged = await _exchange_static_client(
        client, client_id, created.json()["token"], code, verifier, endpoint
    )
    assert exchanged.status_code == 200
    await _assert_token_allows_tool_list(client, str(server_id), exchanged.json()["access_token"])


async def test_runtime_supports_basic_client_auth(
    client: AsyncClient,
    user_headers: dict[str, str],
    repository_repo: InMemoryRepositoryRepository,
    repository_access_repo: InMemoryUserRepositoryAccessRepository,
) -> None:
    user_id = uuid.UUID((await client.get("/api/auth/me", headers=user_headers)).json()["id"])
    repository = _repository()
    repository_repo.add(repository)
    await repository_access_repo.grant(user_id, repository.id)
    created = await client.post(
        "/api/mcp-servers",
        json={"name": "Claude Basic", "repository_id": str(repository.id), "enabled": True},
        headers=user_headers,
    )
    registration = await client.post(
        "/api/mcp/oauth/register",
        json={
            "client_name": "Claude",
            "redirect_uris": ["https://claude.ai/api/oauth/callback"],
            "token_endpoint_auth_method": "client_secret_basic",
        },
    )
    challenge, verifier = _pkce_pair()
    authorized = await _authorize_dynamic_client(
        client, registration.json()["client_id"], created.json()["token"], challenge
    )
    credentials = base64.b64encode(
        f"{registration.json()['client_id']}:{registration.json()['client_secret']}".encode()
    ).decode()

    exchanged = await client.post(
        "/api/mcp/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": parse_qs(urlparse(authorized.headers["location"]).query)["code"][0],
            "redirect_uri": "https://claude.ai/api/oauth/callback",
            "code_verifier": verifier,
        },
        headers={"Authorization": f"Basic {credentials}"},
    )

    assert exchanged.status_code == 200


async def _assert_oauth_metadata(
    client: AsyncClient, server_id: str, endpoint: str, registration
) -> None:
    assert registration.status_code == 201
    assert "client_secret" not in registration.json()
    assert registration.json()["token_endpoint_auth_method"] == "none"
    auth_server = await client.get("/.well-known/oauth-authorization-server")
    assert "client_secret_basic" in auth_server.json()["token_endpoint_auth_methods_supported"]
    metadata = await client.get(
        f"/.well-known/oauth-protected-resource/api/mcp/servers/{server_id}"
    )
    assert metadata.json()["resource"] == endpoint
    denied = await client.post(
        f"/api/mcp/servers/{server_id}",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert denied.status_code == 401
    assert 'scope="repository:read"' in denied.headers["www-authenticate"]


async def _authorize_dynamic_client(
    client: AsyncClient, client_id: str, mcp_token: str, challenge: str
):
    response = await client.post(
        "/api/mcp/oauth/authorize",
        data={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": "https://claude.ai/api/oauth/callback",
            "state": "abc",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "mcp_token": mcp_token,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    return response


async def _authorize_static_client(
    client: AsyncClient, client_id: str, endpoint: str, challenge: str
) -> str:
    response = await client.get(
        "/api/mcp/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
            "state": "abc",
            "resource": endpoint,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    return parse_qs(urlparse(response.headers["location"]).query)["code"][0]


async def _exchange_static_client(
    client: AsyncClient, client_id: str, secret: str, code: str, verifier: str, endpoint: str
):
    credentials = base64.b64encode(f"{client_id}:{secret}".encode()).decode()
    return await client.post(
        "/api/mcp/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
            "code_verifier": verifier,
            "resource": endpoint,
        },
        headers={"Authorization": f"Basic {credentials}"},
    )


async def _assert_token_allows_tool_list(
    client: AsyncClient, server_id: str, access_token: str
) -> None:
    tool_list = await client.post(
        f"/api/mcp/servers/{server_id}",
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert tool_list.status_code == 200
    assert len(tool_list.json()["result"]["tools"]) > 0


def _pkce_pair() -> tuple[str, str]:
    verifier = "test-code-verifier"
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return challenge, verifier


def _unwrap_opaque_test_token(token: str) -> str:
    encoded = token.removeprefix(OAUTH_TOKEN_PREFIX)
    padded = f"{encoded}{'=' * (-len(encoded) % 4)}"
    return base64.urlsafe_b64decode(padded.encode("ascii")).decode("ascii")
