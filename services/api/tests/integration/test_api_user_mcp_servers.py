from __future__ import annotations

import base64
import hashlib
import logging
import uuid
from urllib.parse import parse_qs, urlparse

from app.adapters.primary.http.repository_mcp import get_mcp_telemetry_recorder
from app.application.use_cases.mcp_oauth import OAUTH_TOKEN_PREFIX
from app.application.use_cases.mcp_oauth_clients import static_mcp_client_id
from app.domain.entities import Repository
from app.infrastructure.config import get_settings
from app.main import app
from app.ports.mcp_telemetry import McpToolInvocationRecord
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


class TestUserMcpServersApi:
    async def test_user_crud_and_runtime_endpoint(
        self,
        client: AsyncClient,
        user_headers: dict[str, str],
        repository_repo: InMemoryRepositoryRepository,
        repository_access_repo: InMemoryUserRepositoryAccessRepository,
    ) -> None:
        me = await client.get("/api/auth/me", headers=user_headers)
        user_id = uuid.UUID(me.json()["id"])
        repository = _repository()
        repository_repo.add(repository)
        await repository_access_repo.grant(user_id, repository.id)

        created = await client.post(
            "/api/mcp-servers",
            json={"name": "Claude Demo", "repository_id": str(repository.id), "enabled": True},
            headers=user_headers,
        )

        assert created.status_code == 201
        body = created.json()
        token = body["token"]
        server_id = body["id"]
        assert token.startswith("cappy_mcp_")
        assert body["token_preview"] == token[-8:]

        listed = await client.get("/api/mcp-servers", headers=user_headers)
        assert listed.status_code == 200
        assert "token" not in listed.json()[0]

        init = await client.post(
            f"/api/mcp/servers/{server_id}",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert init.status_code == 200
        assert init.json()["result"]["capabilities"] == {"tools": {"listChanged": False}}

        initialized = await client.post(
            f"/api/mcp/servers/{server_id}",
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert initialized.status_code == 202
        assert initialized.content == b""

        tool_call = await client.post(
            f"/api/mcp/servers/{server_id}",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "repository_search", "arguments": {"query": "foo"}},
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert tool_call.status_code == 200
        assert "repository_search" in tool_call.json()["result"]["content"][0]["text"]

        query_token_call = await client.post(
            f"/api/mcp/servers/{server_id}?mcp_token={token}",
            json={"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
        )
        assert query_token_call.status_code == 200
        tokenized_call = await client.post(
            f"/api/mcp/token/{token}/servers/{server_id}",
            json={"jsonrpc": "2.0", "id": 4, "method": "tools/list"},
        )
        assert tokenized_call.status_code == 200
        tokenized_metadata = await client.get(
            f"/.well-known/oauth-protected-resource/api/mcp/token/{token}/servers/{server_id}"
        )
        assert tokenized_metadata.status_code == 404

    async def test_runtime_records_mcp_tool_telemetry_and_echoes_trace(
        self,
        client: AsyncClient,
        user_headers: dict[str, str],
        repository_repo: InMemoryRepositoryRepository,
        repository_access_repo: InMemoryUserRepositoryAccessRepository,
    ) -> None:
        captured: list[McpToolInvocationRecord] = []
        app.dependency_overrides[get_mcp_telemetry_recorder] = lambda: captured.append
        me = await client.get("/api/auth/me", headers=user_headers)
        user_id = uuid.UUID(me.json()["id"])
        repository = _repository()
        repository_repo.add(repository)
        await repository_access_repo.grant(user_id, repository.id)
        created = await client.post(
            "/api/mcp-servers",
            json={"name": "Claude Telemetry", "repository_id": str(repository.id)},
            headers=user_headers,
        )
        trace_id = uuid.uuid4()

        tool_call = await client.post(
            f"/api/mcp/servers/{created.json()['id']}",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "smart_codebase_graph",
                    "arguments": {"materialized": True, "apiKey": "secret"},
                },
            },
            headers={
                "Authorization": f"Bearer {created.json()['token']}",
                "X-Request-Id": str(trace_id),
                "Mcp-Session-Id": "claude-session",
                "User-Agent": "Claude",
            },
        )

        assert tool_call.status_code == 200
        assert tool_call.headers["x-request-id"] == str(trace_id)
        assert len(captured) == 1
        row = captured[0]
        assert row.trace_id == trace_id
        assert row.user_id == user_id
        assert row.repo_id == repository.id
        assert row.tool_name == "repository_graph"
        assert row.materialized is True
        assert row.caller_user_agent == "Claude"
        assert row.caller_session_id == "claude-session"
        assert row.arguments_sanitized["apiKey"] == "<redacted>"
        assert row.metadata["requested_tool_name"] == "smart_codebase_graph"

    async def test_runtime_supports_claude_oauth_flow(
        self,
        client: AsyncClient,
        user_headers: dict[str, str],
        repository_repo: InMemoryRepositoryRepository,
        repository_access_repo: InMemoryUserRepositoryAccessRepository,
    ) -> None:
        me = await client.get("/api/auth/me", headers=user_headers)
        user_id = uuid.UUID(me.json()["id"])
        repository = _repository()
        repository_repo.add(repository)
        await repository_access_repo.grant(user_id, repository.id)
        created = await client.post(
            "/api/mcp-servers",
            json={"name": "Claude OAuth", "repository_id": str(repository.id), "enabled": True},
            headers=user_headers,
        )
        server_id = created.json()["id"]
        mcp_token = created.json()["token"]
        endpoint = f"http://test/api/mcp/servers/{server_id}"

        challenge, verifier = _pkce_pair()
        registration = await client.post(
            "/api/mcp/oauth/register",
            json={
                "client_name": "Claude",
                "redirect_uris": ["https://claude.ai/api/oauth/callback"],
            },
        )
        assert registration.status_code == 201
        client_id = registration.json()["client_id"]
        assert "client_secret" not in registration.json()
        assert registration.json()["token_endpoint_auth_method"] == "none"
        assert registration.json()["grant_types"] == ["authorization_code"]
        auth_server = await client.get("/.well-known/oauth-authorization-server")
        assert auth_server.status_code == 200
        assert auth_server.json()["grant_types_supported"] == ["authorization_code"]
        assert "none" in auth_server.json()["token_endpoint_auth_methods_supported"]
        assert "client_secret_basic" in auth_server.json()["token_endpoint_auth_methods_supported"]
        assert "client_secret_post" in auth_server.json()["token_endpoint_auth_methods_supported"]

        metadata = await client.get(
            f"/.well-known/oauth-protected-resource/api/mcp/servers/{server_id}"
        )
        assert metadata.status_code == 200
        assert metadata.json()["resource"] == endpoint
        assert metadata.json()["scopes_supported"] == ["repository:read"]
        root_metadata = await client.get("/.well-known/oauth-protected-resource")
        assert root_metadata.status_code == 200
        assert root_metadata.json()["resource"] == "http://test/api/mcp"
        metadata_head = await client.head(
            f"/.well-known/oauth-protected-resource/api/mcp/servers/{server_id}"
        )
        assert metadata_head.status_code == 200

        denied = await client.post(
            f"/api/mcp/servers/{server_id}",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )
        assert denied.status_code == 401
        assert "resource_metadata" in denied.headers["www-authenticate"]
        assert 'scope="repository:read"' in denied.headers["www-authenticate"]
        get_without_token = await client.get(f"/api/mcp/servers/{server_id}")
        assert get_without_token.status_code == 401
        assert "resource_metadata" in get_without_token.headers["www-authenticate"]
        probe = await client.head(f"/api/mcp/servers/{server_id}")
        assert probe.status_code == 401
        assert "resource_metadata" in probe.headers["www-authenticate"]

        authorized = await client.post(
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
        assert authorized.status_code == 303
        location = authorized.headers["location"]
        parsed = parse_qs(urlparse(location).query)
        assert parsed["state"] == ["abc"]

        exchanged = await client.post(
            "/api/mcp/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": parsed["code"][0],
                "client_id": client_id,
                "redirect_uri": "https://claude.ai/api/oauth/callback",
                "code_verifier": verifier,
            },
        )
        assert exchanged.status_code == 200
        assert set(exchanged.json()) == {"access_token", "token_type", "expires_in", "scope"}
        access_token = exchanged.json()["access_token"]
        assert access_token.startswith(OAUTH_TOKEN_PREFIX)
        assert "." not in access_token
        assert exchanged.json()["token_type"] == "Bearer"
        assert exchanged.json()["scope"] == "repository:read"
        payload = jwt.decode(
            _unwrap_opaque_test_token(access_token),
            get_settings().jwt_secret,
            algorithms=[get_settings().jwt_algorithm],
            options={"verify_aud": False},
        )
        assert payload["iss"] == "http://test"
        assert payload["aud"] == endpoint

        tool_list = await client.post(
            f"/api/mcp/servers/{server_id}",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert tool_list.status_code == 200
        assert tool_list.json()["result"]["tools"][0]["name"] == "repository_list_files"
        assert any(
            tool["name"] == "smart_codebase_search" for tool in tool_list.json()["result"]["tools"]
        )
        get_with_token = await client.get(
            f"/api/mcp/servers/{server_id}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "text/event-stream",
            },
        )
        assert get_with_token.status_code == 405
        assert get_with_token.headers["allow"] == "POST"

    async def test_logs_unmapped_mcp_routes_without_token_values(
        self,
        client: AsyncClient,
        caplog,
    ) -> None:
        with caplog.at_level(logging.INFO, logger="app.main"):
            response = await client.get(
                "/api/mcp/token/cappy_mcp_secret-value/servers/not-found?mcp_token=secret",
                headers={"User-Agent": "python-httpx/0.28.1"},
            )

        app_logs = "\n".join(
            record.getMessage() for record in caplog.records if record.name == "app.main"
        )
        assert response.status_code in {404, 405}
        assert "MCP route miss" in app_logs
        assert "cappy_mcp_***" in app_logs
        assert "secret-value" not in app_logs
        assert "query_keys=mcp_token" in app_logs

    async def test_runtime_supports_static_claude_client_credentials(
        self,
        client: AsyncClient,
        user_headers: dict[str, str],
        repository_repo: InMemoryRepositoryRepository,
        repository_access_repo: InMemoryUserRepositoryAccessRepository,
    ) -> None:
        me = await client.get("/api/auth/me", headers=user_headers)
        user_id = uuid.UUID(me.json()["id"])
        repository = _repository()
        repository_repo.add(repository)
        await repository_access_repo.grant(user_id, repository.id)
        created = await client.post(
            "/api/mcp-servers",
            json={"name": "Claude Static", "repository_id": str(repository.id), "enabled": True},
            headers=user_headers,
        )
        server_id = uuid.UUID(created.json()["id"])
        mcp_token = created.json()["token"]
        endpoint = f"http://test/api/mcp/servers/{server_id}"
        client_id = static_mcp_client_id(server_id)
        challenge, verifier = _pkce_pair()

        auto_authorized = await client.get(
            "/api/mcp/oauth/authorize",
            params={
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
                "state": "abc",
                "resource": endpoint,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "scope": "repository:read",
            },
            follow_redirects=False,
        )
        assert auto_authorized.status_code == 303
        code = parse_qs(urlparse(auto_authorized.headers["location"]).query)["code"][0]
        wrong_credentials = base64.b64encode(f"{client_id}:wrong".encode()).decode()
        rejected = await client.post(
            "/api/mcp/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
                "code_verifier": verifier,
                "resource": endpoint,
            },
            headers={"Authorization": f"Basic {wrong_credentials}"},
        )
        assert rejected.status_code == 400

        credentials = base64.b64encode(f"{client_id}:{mcp_token}".encode()).decode()
        exchanged = await client.post(
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
        assert exchanged.status_code == 200
        assert set(exchanged.json()) == {"access_token", "token_type", "expires_in", "scope"}

        tool_list = await client.post(
            f"/api/mcp/servers/{server_id}",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers={"Authorization": f"Bearer {exchanged.json()['access_token']}"},
        )
        assert tool_list.status_code == 200
        assert len(tool_list.json()["result"]["tools"]) > 0

    async def test_runtime_supports_basic_client_auth(
        self,
        client: AsyncClient,
        user_headers: dict[str, str],
        repository_repo: InMemoryRepositoryRepository,
        repository_access_repo: InMemoryUserRepositoryAccessRepository,
    ) -> None:
        me = await client.get("/api/auth/me", headers=user_headers)
        user_id = uuid.UUID(me.json()["id"])
        repository = _repository()
        repository_repo.add(repository)
        await repository_access_repo.grant(user_id, repository.id)
        created = await client.post(
            "/api/mcp-servers",
            json={"name": "Claude Basic", "repository_id": str(repository.id), "enabled": True},
            headers=user_headers,
        )
        server_id = created.json()["id"]
        endpoint = f"http://test/api/mcp/servers/{server_id}"
        mcp_token = created.json()["token"]
        challenge, verifier = _pkce_pair()
        registration = await client.post(
            "/api/mcp/oauth/register",
            json={
                "client_name": "Claude",
                "redirect_uris": ["https://claude.ai/api/oauth/callback"],
                "token_endpoint_auth_method": "client_secret_basic",
            },
        )
        client_id = registration.json()["client_id"]
        client_secret = registration.json()["client_secret"]
        authorized = await client.post(
            "/api/mcp/oauth/authorize",
            data={
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": "https://claude.ai/api/oauth/callback",
                "state": "abc",
                "resource": endpoint,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "mcp_token": mcp_token,
            },
            follow_redirects=False,
        )
        location = authorized.headers["location"]
        code = parse_qs(urlparse(location).query)["code"][0]
        credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

        exchanged = await client.post(
            "/api/mcp/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": "https://claude.ai/api/oauth/callback",
                "code_verifier": verifier,
            },
            headers={"Authorization": f"Basic {credentials}"},
        )

        assert exchanged.status_code == 200

    async def test_runtime_rejects_wrong_token(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        repository_repo: InMemoryRepositoryRepository,
    ) -> None:
        repository = _repository()
        repository_repo.add(repository)
        created = await client.post(
            "/api/mcp-servers",
            json={"name": "Admin MCP", "repository_id": str(repository.id), "enabled": True},
            headers=admin_headers,
        )
        server_id = created.json()["id"]

        response = await client.post(
            f"/api/mcp/servers/{server_id}",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"Authorization": "Bearer wrong"},
        )

        assert response.status_code == 401

    async def test_runtime_rejects_invalid_json_without_500(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        repository_repo: InMemoryRepositoryRepository,
    ) -> None:
        repository = _repository()
        repository_repo.add(repository)
        created = await client.post(
            "/api/mcp-servers",
            json={"name": "Invalid JSON MCP", "repository_id": str(repository.id), "enabled": True},
            headers=admin_headers,
        )
        token = created.json()["token"]
        server_id = created.json()["id"]

        response = await client.post(
            f"/api/mcp/servers/{server_id}",
            content="{bad",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )

        assert response.status_code == 400


def _pkce_pair() -> tuple[str, str]:
    verifier = "test-code-verifier"
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return challenge, verifier


def _unwrap_opaque_test_token(token: str) -> str:
    encoded = token.removeprefix(OAUTH_TOKEN_PREFIX)
    padded = f"{encoded}{'=' * (-len(encoded) % 4)}"
    return base64.urlsafe_b64decode(padded.encode("ascii")).decode("ascii")
