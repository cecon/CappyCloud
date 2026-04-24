"""Integration tests — full HTTP stack with dependency_overrides.

Uses httpx.AsyncClient against the real FastAPI app, but with all
external dependencies replaced by in-memory fakes. No DB or network required.
"""

from __future__ import annotations

import pytest
from app.adapters.primary.http.deps import (
    get_agent,
    get_agent_repo,
    get_conv_repo,
    get_msg_repo,
    get_password_service,
    get_token_service,
    get_user_agent_profile_repo,
    get_user_repo,
)
from app.main import app
from httpx import ASGITransport, AsyncClient

from tests.conftest import (
    FakeAgent,
    FakePasswordService,
    FakeTokenService,
    InMemoryAgentRepository,
    InMemoryConversationRepository,
    InMemoryMessageRepository,
    InMemoryUserAgentProfileRepository,
    InMemoryUserRepository,
)


@pytest.fixture
async def client() -> AsyncClient:
    """HTTP client with all external dependencies replaced by in-memory fakes."""
    user_repo = InMemoryUserRepository()
    user_agent_profile_repo = InMemoryUserAgentProfileRepository()
    conv_repo = InMemoryConversationRepository()
    msg_repo = InMemoryMessageRepository()

    app.dependency_overrides[get_user_repo] = lambda: user_repo
    app.dependency_overrides[get_user_agent_profile_repo] = lambda: user_agent_profile_repo
    app.dependency_overrides[get_conv_repo] = lambda: conv_repo
    app.dependency_overrides[get_msg_repo] = lambda: msg_repo
    app.dependency_overrides[get_password_service] = lambda: FakePasswordService()
    app.dependency_overrides[get_token_service] = lambda: FakeTokenService()
    app.dependency_overrides[get_agent] = lambda: FakeAgent()
    app.dependency_overrides[get_agent_repo] = lambda: InMemoryAgentRepository()

    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c  # type: ignore[misc]

    app.dependency_overrides.clear()


class TestHealth:
    async def test_health(self, client: AsyncClient) -> None:
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


class TestAuthEndpoints:
    async def test_register_success(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/auth/register",
            json={"email": "new@test.com", "password": "password123"},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["email"] == "new@test.com"
        assert "id" in data

    async def test_register_invalid_email(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/auth/register",
            json={"email": "not-an-email", "password": "password123"},
        )
        assert r.status_code == 422

    async def test_register_short_password(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/auth/register",
            json={"email": "a@b.com", "password": "short"},
        )
        assert r.status_code == 422

    async def test_login_success(self, client: AsyncClient) -> None:
        await client.post(
            "/api/auth/register",
            json={"email": "login@test.com", "password": "password123"},
        )
        r = await client.post(
            "/api/auth/login",
            data={"username": "login@test.com", "password": "password123"},
        )
        assert r.status_code == 200
        assert "access_token" in r.json()

    async def test_login_wrong_password(self, client: AsyncClient) -> None:
        await client.post(
            "/api/auth/register",
            json={"email": "wrong@test.com", "password": "goodpassword"},
        )
        r = await client.post(
            "/api/auth/login",
            data={"username": "wrong@test.com", "password": "badpassword"},
        )
        assert r.status_code == 401

    async def test_me_unauthenticated(self, client: AsyncClient) -> None:
        r = await client.get("/api/auth/me")
        assert r.status_code == 401

    async def test_me_authenticated(self, client: AsyncClient) -> None:
        await client.post(
            "/api/auth/register",
            json={"email": "me@test.com", "password": "password123"},
        )
        login = await client.post(
            "/api/auth/login",
            data={"username": "me@test.com", "password": "password123"},
        )
        token = login.json()["access_token"]
        r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["email"] == "me@test.com"


class TestConversationEndpoints:
    @pytest.fixture
    async def auth_headers(self, client: AsyncClient) -> dict[str, str]:
        """Register and login, return auth headers."""
        await client.post(
            "/api/auth/register",
            json={"email": "conv@test.com", "password": "password123"},
        )
        r = await client.post(
            "/api/auth/login",
            data={"username": "conv@test.com", "password": "password123"},
        )
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    async def test_list_conversations_empty(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.get("/api/conversations", headers=auth_headers)
        assert r.status_code == 200
        assert r.json() == []

    async def test_create_conversation(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.post(
            "/api/conversations",
            json={"title": "Meu chat"},
            headers=auth_headers,
        )
        assert r.status_code == 201
        assert r.json()["title"] == "Meu chat"

    async def test_list_messages_not_found(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        fake_id = "00000000-0000-0000-0000-000000000000"
        r = await client.get(f"/api/conversations/{fake_id}/messages", headers=auth_headers)
        assert r.status_code == 404

    async def test_stream_message(self, client: AsyncClient, auth_headers: dict[str, str]) -> None:
        conv_r = await client.post(
            "/api/conversations",
            json={"title": "Stream chat"},
            headers=auth_headers,
        )
        conv_id = conv_r.json()["id"]
        r = await client.post(
            f"/api/conversations/{conv_id}/messages/stream",
            json={"content": "Olá agente"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]
        assert len(r.content) > 0
