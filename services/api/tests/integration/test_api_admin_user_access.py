"""Integration HTTP — /api/admin/users/{user_id}/access (ADR-005 §2, ADR-006 §3)."""

from __future__ import annotations

import uuid

import pytest
from app.domain.entities import ModelTier, UserRole
from httpx import AsyncClient

from tests.conftest import (
    InMemoryUserAiModelAccessRepository,
    InMemoryUserRepository,
    InMemoryUserRepositoryAccessRepository,
    InMemoryUserSandboxAccessRepository,
)
from tests.integration.conftest import _StubModelsByTierLookup, seed_user


@pytest.fixture
async def target_user_id(user_repo: InMemoryUserRepository) -> uuid.UUID:
    user = await seed_user(user_repo, "target@test.com", role=UserRole.USER)
    return user.id


class TestSandboxAccessEndpoints:
    async def test_list_requires_admin(
        self,
        client: AsyncClient,
        target_user_id: uuid.UUID,
        user_headers: dict[str, str],
    ) -> None:
        r = await client.get(
            f"/api/admin/users/{target_user_id}/access/sandboxes", headers=user_headers
        )
        assert r.status_code == 403

    async def test_grant_revoke_roundtrip(
        self,
        client: AsyncClient,
        target_user_id: uuid.UUID,
        admin_headers: dict[str, str],
        sandbox_access_repo: InMemoryUserSandboxAccessRepository,
    ) -> None:
        sid = uuid.uuid4()

        # GRANT
        r = await client.post(
            f"/api/admin/users/{target_user_id}/access/sandboxes/{sid}",
            headers=admin_headers,
        )
        assert r.status_code == 204
        assert await sandbox_access_repo.has_access(target_user_id, sid)

        # LIST devolve o id concedido
        r = await client.get(
            f"/api/admin/users/{target_user_id}/access/sandboxes", headers=admin_headers
        )
        assert r.status_code == 200
        assert r.json() == [str(sid)]

        # REVOKE
        r = await client.delete(
            f"/api/admin/users/{target_user_id}/access/sandboxes/{sid}",
            headers=admin_headers,
        )
        assert r.status_code == 204
        assert not await sandbox_access_repo.has_access(target_user_id, sid)

    async def test_grant_is_idempotent(
        self,
        client: AsyncClient,
        target_user_id: uuid.UUID,
        admin_headers: dict[str, str],
        sandbox_access_repo: InMemoryUserSandboxAccessRepository,
    ) -> None:
        sid = uuid.uuid4()

        r1 = await client.post(
            f"/api/admin/users/{target_user_id}/access/sandboxes/{sid}",
            headers=admin_headers,
        )
        r2 = await client.post(
            f"/api/admin/users/{target_user_id}/access/sandboxes/{sid}",
            headers=admin_headers,
        )

        assert r1.status_code == 204 and r2.status_code == 204
        # Lista ainda tem exatamente 1 entrada — sem duplicação:
        ids = await sandbox_access_repo.list_resources_for_user(target_user_id)
        assert ids == [sid]

    async def test_revoke_missing_returns_404(
        self,
        client: AsyncClient,
        target_user_id: uuid.UUID,
        admin_headers: dict[str, str],
    ) -> None:
        r = await client.delete(
            f"/api/admin/users/{target_user_id}/access/sandboxes/{uuid.uuid4()}",
            headers=admin_headers,
        )
        assert r.status_code == 404


class TestRepositoryAccessEndpoints:
    async def test_grant_then_list(
        self,
        client: AsyncClient,
        target_user_id: uuid.UUID,
        admin_headers: dict[str, str],
        repository_access_repo: InMemoryUserRepositoryAccessRepository,
    ) -> None:
        rid = uuid.uuid4()

        r = await client.post(
            f"/api/admin/users/{target_user_id}/access/repositories/{rid}",
            headers=admin_headers,
        )
        assert r.status_code == 204

        r = await client.get(
            f"/api/admin/users/{target_user_id}/access/repositories",
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json() == [str(rid)]
        assert await repository_access_repo.has_access(target_user_id, rid)

    async def test_revoke_removes(
        self,
        client: AsyncClient,
        target_user_id: uuid.UUID,
        admin_headers: dict[str, str],
        repository_access_repo: InMemoryUserRepositoryAccessRepository,
    ) -> None:
        rid = uuid.uuid4()
        await repository_access_repo.grant(target_user_id, rid)

        r = await client.delete(
            f"/api/admin/users/{target_user_id}/access/repositories/{rid}",
            headers=admin_headers,
        )
        assert r.status_code == 204
        assert await repository_access_repo.list_resources_for_user(target_user_id) == []


class TestAiModelAccessEndpoints:
    async def test_grant_then_revoke(
        self,
        client: AsyncClient,
        target_user_id: uuid.UUID,
        admin_headers: dict[str, str],
        ai_model_access_repo: InMemoryUserAiModelAccessRepository,
    ) -> None:
        mid = uuid.uuid4()

        r = await client.post(
            f"/api/admin/users/{target_user_id}/access/ai-models/{mid}",
            headers=admin_headers,
        )
        assert r.status_code == 204
        assert await ai_model_access_repo.has_access(target_user_id, mid)

        r = await client.delete(
            f"/api/admin/users/{target_user_id}/access/ai-models/{mid}",
            headers=admin_headers,
        )
        assert r.status_code == 204
        assert not await ai_model_access_repo.has_access(target_user_id, mid)


class TestBulkGrantByTier:
    async def test_user_without_admin_blocked(
        self,
        client: AsyncClient,
        target_user_id: uuid.UUID,
        user_headers: dict[str, str],
    ) -> None:
        r = await client.post(
            f"/api/admin/users/{target_user_id}/access/ai-models/bulk-tier",
            json={"tier": "free"},
            headers=user_headers,
        )
        assert r.status_code == 403

    async def test_grants_all_free_models(
        self,
        client: AsyncClient,
        target_user_id: uuid.UUID,
        admin_headers: dict[str, str],
        ai_model_access_repo: InMemoryUserAiModelAccessRepository,
        models_by_tier_lookup: _StubModelsByTierLookup,
    ) -> None:
        free_ids = [uuid.uuid4() for _ in range(3)]
        paid_ids = [uuid.uuid4()]
        models_by_tier_lookup._mapping = {
            ModelTier.FREE: free_ids,
            ModelTier.PAID: paid_ids,
        }

        r = await client.post(
            f"/api/admin/users/{target_user_id}/access/ai-models/bulk-tier",
            json={"tier": "free"},
            headers=admin_headers,
        )

        assert r.status_code == 200
        assert r.json() == {"granted": 3}
        # Apenas os FREE foram liberados — PAID continua sem acesso:
        liberados = set(await ai_model_access_repo.list_resources_for_user(target_user_id))
        assert liberados == set(free_ids)
        for pid in paid_ids:
            assert not await ai_model_access_repo.has_access(target_user_id, pid)

    async def test_bulk_is_idempotent(
        self,
        client: AsyncClient,
        target_user_id: uuid.UUID,
        admin_headers: dict[str, str],
        ai_model_access_repo: InMemoryUserAiModelAccessRepository,
        models_by_tier_lookup: _StubModelsByTierLookup,
    ) -> None:
        free_ids = [uuid.uuid4(), uuid.uuid4()]
        models_by_tier_lookup._mapping = {ModelTier.FREE: free_ids}

        r1 = await client.post(
            f"/api/admin/users/{target_user_id}/access/ai-models/bulk-tier",
            json={"tier": "free"},
            headers=admin_headers,
        )
        r2 = await client.post(
            f"/api/admin/users/{target_user_id}/access/ai-models/bulk-tier",
            json={"tier": "free"},
            headers=admin_headers,
        )

        assert r1.json() == {"granted": 2} and r2.json() == {"granted": 2}
        liberados = await ai_model_access_repo.list_resources_for_user(target_user_id)
        # Ainda 2, sem duplicação:
        assert set(liberados) == set(free_ids) and len(liberados) == 2

    async def test_unknown_tier_returns_zero(
        self,
        client: AsyncClient,
        target_user_id: uuid.UUID,
        admin_headers: dict[str, str],
    ) -> None:
        r = await client.post(
            f"/api/admin/users/{target_user_id}/access/ai-models/bulk-tier",
            json={"tier": "unknown"},
            headers=admin_headers,
        )

        assert r.status_code == 200
        assert r.json() == {"granted": 0}

    async def test_invalid_tier_returns_422(
        self,
        client: AsyncClient,
        target_user_id: uuid.UUID,
        admin_headers: dict[str, str],
    ) -> None:
        r = await client.post(
            f"/api/admin/users/{target_user_id}/access/ai-models/bulk-tier",
            json={"tier": "platinum"},
            headers=admin_headers,
        )
        assert r.status_code == 422
