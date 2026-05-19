"""Integration HTTP — endpoints de auth/health (ADR-005)."""

from __future__ import annotations

from app.domain.entities import UserRole
from httpx import AsyncClient

from tests.conftest import InMemoryUserRepository
from tests.integration.conftest import seed_user


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
        assert data["must_change_password"] is True
        assert "id" in data

    async def test_register_can_disable_first_login_password_change(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        r = await client.post(
            "/api/auth/register",
            json={
                "email": "ready@test.com",
                "password": "password123",
                "must_change_password": False,
            },
            headers=admin_headers,
        )
        assert r.status_code == 201
        assert r.json()["must_change_password"] is False

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
        assert body["must_change_password"] is False

    async def test_me_returns_admin_role(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        r = await client.get("/api/auth/me", headers=admin_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == "admin@test.com"
        assert body["role"] == "admin"

    async def test_change_password_clears_first_login_lock(
        self,
        client: AsyncClient,
        user_repo: InMemoryUserRepository,
    ) -> None:
        await seed_user(
            user_repo,
            "firstlogin@test.com",
            role=UserRole.USER,
            must_change_password=True,
        )
        login = await client.post(
            "/api/auth/login",
            data={"username": "firstlogin@test.com", "password": "password123"},
        )
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        locked = await client.get("/api/conversations", headers=headers)
        assert locked.status_code == 403

        changed = await client.post(
            "/api/auth/change-password",
            json={"current_password": "password123", "new_password": "newpassword123"},
            headers=headers,
        )
        assert changed.status_code == 200
        assert changed.json()["must_change_password"] is False

        old_login = await client.post(
            "/api/auth/login",
            data={"username": "firstlogin@test.com", "password": "password123"},
        )
        assert old_login.status_code == 401

        new_login = await client.post(
            "/api/auth/login",
            data={"username": "firstlogin@test.com", "password": "newpassword123"},
        )
        assert new_login.status_code == 200

    async def test_change_password_rejects_wrong_current_password(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        r = await client.post(
            "/api/auth/change-password",
            json={"current_password": "badpassword", "new_password": "newpassword123"},
            headers=user_headers,
        )
        assert r.status_code == 400
