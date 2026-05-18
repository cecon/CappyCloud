"""Integration HTTP — endpoints de auth/health (ADR-005)."""

from __future__ import annotations

from httpx import AsyncClient


class TestHealth:
    async def test_health(self, client: AsyncClient) -> None:
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


class TestAuthEndpoints:
    async def test_register_requires_authentication(self, client: AsyncClient) -> None:
        # ADR-005: /register não é público.
        r = await client.post(
            "/api/auth/register",
            json={"email": "new@test.com", "password": "password123"},
        )
        assert r.status_code == 401

    async def test_register_requires_admin_role(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        r = await client.post(
            "/api/auth/register",
            json={"email": "new@test.com", "password": "password123"},
            headers=user_headers,
        )
        assert r.status_code == 403

    async def test_register_success_as_admin(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        r = await client.post(
            "/api/auth/register",
            json={"email": "new@test.com", "password": "password123"},
            headers=admin_headers,
        )
        assert r.status_code == 201
        data = r.json()
        assert data["email"] == "new@test.com"
        # Sem role no body → default USER (ADR-005 §1).
        assert data["role"] == "user"
        assert "id" in data

    async def test_admin_can_create_another_admin(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        r = await client.post(
            "/api/auth/register",
            json={
                "email": "another-admin@test.com",
                "password": "password123",
                "role": "admin",
            },
            headers=admin_headers,
        )
        assert r.status_code == 201
        assert r.json()["role"] == "admin"

    async def test_register_invalid_email(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        r = await client.post(
            "/api/auth/register",
            json={"email": "not-an-email", "password": "password123"},
            headers=admin_headers,
        )
        assert r.status_code == 422

    async def test_register_short_password(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        r = await client.post(
            "/api/auth/register",
            json={"email": "a@b.com", "password": "short"},
            headers=admin_headers,
        )
        assert r.status_code == 422

    async def test_register_rejects_unknown_role(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        r = await client.post(
            "/api/auth/register",
            json={
                "email": "weird@test.com",
                "password": "password123",
                "role": "superuser",
            },
            headers=admin_headers,
        )
        assert r.status_code == 422

    async def test_login_success(self, client: AsyncClient, user_headers: dict[str, str]) -> None:
        # user_headers garante user "regular@test.com" seedado.
        assert "Authorization" in user_headers
        r = await client.post(
            "/api/auth/login",
            data={"username": "regular@test.com", "password": "password123"},
        )
        assert r.status_code == 200
        assert "access_token" in r.json()

    async def test_login_wrong_password(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        assert "Authorization" in user_headers
        r = await client.post(
            "/api/auth/login",
            data={"username": "regular@test.com", "password": "badpassword"},
        )
        assert r.status_code == 401

    async def test_me_unauthenticated(self, client: AsyncClient) -> None:
        r = await client.get("/api/auth/me")
        assert r.status_code == 401

    async def test_me_returns_user_role(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        r = await client.get("/api/auth/me", headers=user_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == "regular@test.com"
        assert body["role"] == "user"

    async def test_me_returns_admin_role(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        r = await client.get("/api/auth/me", headers=admin_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == "admin@test.com"
        assert body["role"] == "admin"
