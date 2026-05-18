"""Integration HTTP — /api/admin/users (ADR-005)."""

from __future__ import annotations

import uuid

from app.domain.entities import UserRole
from httpx import AsyncClient

from tests.conftest import InMemoryUserRepository
from tests.integration.conftest import seed_user


class TestAdminUsersEndpoints:
    async def test_list_requires_admin(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        r = await client.get("/api/admin/users", headers=user_headers)
        assert r.status_code == 403

    async def test_list_returns_users_for_admin(
        self,
        client: AsyncClient,
        user_repo: InMemoryUserRepository,
        admin_headers: dict[str, str],
    ) -> None:
        await seed_user(user_repo, "extra@test.com", role=UserRole.USER)

        r = await client.get("/api/admin/users", headers=admin_headers)

        assert r.status_code == 200
        rows = r.json()
        emails = {u["email"] for u in rows}
        assert {"admin@test.com", "extra@test.com"}.issubset(emails)
        # Papéis serializados como strings minúsculas (contrato ADR-005):
        by_email = {u["email"]: u for u in rows}
        assert by_email["admin@test.com"]["role"] == "admin"
        assert by_email["extra@test.com"]["role"] == "user"

    async def test_patch_role_requires_admin(
        self,
        client: AsyncClient,
        user_repo: InMemoryUserRepository,
        user_headers: dict[str, str],
    ) -> None:
        target = await seed_user(user_repo, "tgt@test.com", role=UserRole.USER)
        r = await client.patch(
            f"/api/admin/users/{target.id}/role",
            json={"role": "admin"},
            headers=user_headers,
        )
        assert r.status_code == 403

    async def test_patch_role_promotes_user(
        self,
        client: AsyncClient,
        user_repo: InMemoryUserRepository,
        admin_headers: dict[str, str],
    ) -> None:
        target = await seed_user(user_repo, "promoteme@test.com", role=UserRole.USER)

        r = await client.patch(
            f"/api/admin/users/{target.id}/role",
            json={"role": "admin"},
            headers=admin_headers,
        )

        assert r.status_code == 200
        body = r.json()
        assert body["role"] == "admin"
        assert body["email"] == "promoteme@test.com"
        # Persistido — buscar de novo via repo:
        reread = await user_repo.get_by_id(target.id)
        assert reread is not None and reread.is_admin

    async def test_patch_role_blocks_self_demotion(
        self,
        client: AsyncClient,
        user_repo: InMemoryUserRepository,
        admin_headers: dict[str, str],
    ) -> None:
        admin = await user_repo.get_by_email("admin@test.com")
        assert admin is not None

        r = await client.patch(
            f"/api/admin/users/{admin.id}/role",
            json={"role": "user"},
            headers=admin_headers,
        )

        assert r.status_code == 409
        # Estado preservado:
        reread = await user_repo.get_by_id(admin.id)
        assert reread is not None and reread.is_admin

    async def test_patch_role_404_for_unknown_user(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        r = await client.patch(
            f"/api/admin/users/{uuid.uuid4()}/role",
            json={"role": "admin"},
            headers=admin_headers,
        )
        assert r.status_code == 404

    async def test_patch_role_rejects_unknown_role(
        self,
        client: AsyncClient,
        user_repo: InMemoryUserRepository,
        admin_headers: dict[str, str],
    ) -> None:
        target = await seed_user(user_repo, "weirdrole@test.com", role=UserRole.USER)

        r = await client.patch(
            f"/api/admin/users/{target.id}/role",
            json={"role": "superuser"},
            headers=admin_headers,
        )

        assert r.status_code == 422
