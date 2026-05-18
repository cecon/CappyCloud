"""Integration HTTP — /api/admin/providers, /api/admin/models (ADR-006).

Cobre a porta admin: garante que **só ADMIN** acessa essas rotas. As
queries SQL em si são triviais (``select(AiModel)``) e não justificam
fixture com DB — a regra de negócio crítica aqui é o gate de papel.
"""

from __future__ import annotations

import uuid

from httpx import AsyncClient


class TestAdminAiCatalogRoleGuard:
    async def test_list_providers_blocks_non_admin(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        r = await client.get("/api/admin/providers", headers=user_headers)
        assert r.status_code == 403

    async def test_sync_provider_blocks_non_admin(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        r = await client.post(f"/api/admin/providers/{uuid.uuid4()}/sync", headers=user_headers)
        assert r.status_code == 403

    async def test_list_models_blocks_non_admin(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        r = await client.get("/api/admin/models", headers=user_headers)
        assert r.status_code == 403

    async def test_patch_model_blocks_non_admin(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        r = await client.patch(
            f"/api/admin/models/{uuid.uuid4()}",
            json={"active": False},
            headers=user_headers,
        )
        assert r.status_code == 403

    async def test_endpoints_require_authentication(self, client: AsyncClient) -> None:
        # Sem token, sequer chega ao gate de role — 401:
        r = await client.get("/api/admin/providers")
        assert r.status_code == 401
        r = await client.get("/api/admin/models")
        assert r.status_code == 401
