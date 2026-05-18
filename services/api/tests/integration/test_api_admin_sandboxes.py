"""Integration HTTP — /api/admin/sandboxes (ADR-004)."""

from __future__ import annotations

from app.domain.entities import ContainerStatus
from httpx import AsyncClient

from tests.conftest import InMemorySandboxRepository


class TestAdminSandboxesEndpoints:
    async def test_list_requires_admin(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        r = await client.get("/api/admin/sandboxes", headers=user_headers)
        assert r.status_code == 403

    async def test_full_lifecycle(self, client: AsyncClient, admin_headers: dict[str, str]) -> None:
        # 1. Lista vazia
        r = await client.get("/api/admin/sandboxes", headers=admin_headers)
        assert r.status_code == 200 and r.json() == []

        # 2. Cria
        create_payload = {
            "name": "alpha",
            "runtime": "compose",
            "image": "cappy/sandbox:latest",
            "env_vars": {"FOO": "bar"},
        }
        r = await client.post("/api/admin/sandboxes", json=create_payload, headers=admin_headers)
        assert r.status_code == 201
        created = r.json()
        assert created["name"] == "alpha"
        assert created["container_status"] == "not_created"
        assert created["env_vars"] == {"FOO": "bar"}
        sandbox_id = created["id"]

        # 3. Duplicata rejeitada
        r = await client.post("/api/admin/sandboxes", json=create_payload, headers=admin_headers)
        assert r.status_code == 409

        # 4. Update parcial
        r = await client.patch(
            f"/api/admin/sandboxes/{sandbox_id}",
            json={"image": "cappy/sandbox:v2"},
            headers=admin_headers,
        )
        assert r.status_code == 200 and r.json()["image"] == "cappy/sandbox:v2"

        # 5. Boot — transiciona para configured (stub)
        r = await client.post(f"/api/admin/sandboxes/{sandbox_id}/boot", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["container_status"] == "configured"

        # 6. Delete bloqueado porque container_status é "configured"
        r = await client.delete(f"/api/admin/sandboxes/{sandbox_id}", headers=admin_headers)
        assert r.status_code == 409

        # 7. Stop volta para stopped
        r = await client.post(f"/api/admin/sandboxes/{sandbox_id}/stop", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["container_status"] == "stopped"

        # 8. Delete agora passa
        r = await client.delete(f"/api/admin/sandboxes/{sandbox_id}", headers=admin_headers)
        assert r.status_code == 204

    async def test_clone_copies_config_resets_runtime(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        sandbox_repo: InMemorySandboxRepository,
    ) -> None:
        r = await client.post(
            "/api/admin/sandboxes",
            json={
                "name": "origin",
                "runtime": "compose",
                "image": "cappy/sandbox:latest",
                "env_vars": {"K": "V"},
            },
            headers=admin_headers,
        )
        assert r.status_code == 201
        sandbox_id = r.json()["id"]

        from uuid import UUID

        await sandbox_repo.update_container_status(UUID(sandbox_id), ContainerStatus.RUNNING)

        r = await client.post(
            f"/api/admin/sandboxes/{sandbox_id}/clone",
            json={"new_name": "copy"},
            headers=admin_headers,
        )
        assert r.status_code == 201
        clone = r.json()
        assert clone["name"] == "copy"
        assert clone["image"] == "cappy/sandbox:latest"
        assert clone["env_vars"] == {"K": "V"}
        # Runtime state foi resetado:
        assert clone["container_status"] == "not_created"

    async def test_swarm_runtime_returns_501(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
    ) -> None:
        r = await client.post(
            "/api/admin/sandboxes",
            json={
                "name": "swarm-only",
                "runtime": "swarm",
                "image": "cappy/sandbox:latest",
            },
            headers=admin_headers,
        )
        assert r.status_code == 201
        sandbox_id = r.json()["id"]

        # Boot com runtime swarm não configurado → 502 (RuntimeFailureError).
        r = await client.post(f"/api/admin/sandboxes/{sandbox_id}/boot", headers=admin_headers)
        assert r.status_code == 502
