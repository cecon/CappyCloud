"""Integration HTTP — /api/admin/sandboxes/{id}/skills e /agents (ADR-004 §6)."""

from __future__ import annotations

import uuid

from httpx import AsyncClient

from tests.conftest import FakeSandboxBootstrap


class TestAdminSandboxSkillsEndpoints:
    async def test_requires_admin(self, client: AsyncClient, user_headers: dict[str, str]) -> None:
        sb_id = uuid.uuid4()
        r = await client.get(f"/api/admin/sandboxes/{sb_id}/skills", headers=user_headers)
        assert r.status_code == 403

    async def test_full_crud_lifecycle(
        self,
        client: AsyncClient,
        super_admin_headers: dict[str, str],
    ) -> None:
        r = await client.post(
            "/api/admin/sandboxes",
            json={"name": "sk-test", "runtime": "compose", "image": "cappy/sandbox:latest"},
            headers=super_admin_headers,
        )
        sb_id = r.json()["id"]

        r = await client.get(f"/api/admin/sandboxes/{sb_id}/skills", headers=super_admin_headers)
        assert r.status_code == 200 and r.json() == []

        r = await client.post(
            f"/api/admin/sandboxes/{sb_id}/skills",
            json={
                "name": "naming-conventions",
                "description": "snake_case em Python",
                "content": "# Naming\n- Python: snake_case\n- TS: camelCase",
                "enabled": True,
            },
            headers=super_admin_headers,
        )
        assert r.status_code == 201
        skill_id = r.json()["id"]
        assert r.json()["name"] == "naming-conventions"

        # Duplicata rejeitada (mesmo nome dentro da sandbox)
        r = await client.post(
            f"/api/admin/sandboxes/{sb_id}/skills",
            json={"name": "naming-conventions", "content": "x"},
            headers=super_admin_headers,
        )
        assert r.status_code == 409

        # Update
        r = await client.put(
            f"/api/admin/sandboxes/{sb_id}/skills/{skill_id}",
            json={
                "name": "naming-conventions",
                "description": "atualizado",
                "content": "# Naming v2",
                "enabled": False,
            },
            headers=super_admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["enabled"] is False
        assert r.json()["content"] == "# Naming v2"

        # Delete
        r = await client.delete(
            f"/api/admin/sandboxes/{sb_id}/skills/{skill_id}", headers=super_admin_headers
        )
        assert r.status_code == 204

    async def test_plain_admin_can_list_but_cannot_mutate_skills(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        super_admin_headers: dict[str, str],
    ) -> None:
        r = await client.post(
            "/api/admin/sandboxes",
            json={"name": "sk-perm", "runtime": "compose", "image": "cappy/sandbox:latest"},
            headers=super_admin_headers,
        )
        sb_id = r.json()["id"]

        r = await client.get(f"/api/admin/sandboxes/{sb_id}/skills", headers=admin_headers)
        assert r.status_code == 200

        r = await client.post(
            f"/api/admin/sandboxes/{sb_id}/skills",
            json={"name": "blocked", "content": "x"},
            headers=admin_headers,
        )
        assert r.status_code == 403

        r = await client.post(
            f"/api/admin/sandboxes/{sb_id}/skills",
            json={"name": "allowed", "content": "x"},
            headers=super_admin_headers,
        )
        skill_id = r.json()["id"]

        r = await client.put(
            f"/api/admin/sandboxes/{sb_id}/skills/{skill_id}",
            json={"name": "allowed", "content": "y"},
            headers=admin_headers,
        )
        assert r.status_code == 403

        r = await client.delete(
            f"/api/admin/sandboxes/{sb_id}/skills/{skill_id}",
            headers=admin_headers,
        )
        assert r.status_code == 403

    async def test_rejects_invalid_name(
        self, client: AsyncClient, super_admin_headers: dict[str, str]
    ) -> None:
        r = await client.post(
            "/api/admin/sandboxes",
            json={"name": "sk-name", "runtime": "compose", "image": "x"},
            headers=super_admin_headers,
        )
        sb_id = r.json()["id"]
        r = await client.post(
            f"/api/admin/sandboxes/{sb_id}/skills",
            json={"name": "tem espaço", "content": "x"},
            headers=super_admin_headers,
        )
        assert r.status_code == 422


class TestAdminGlobalSkillsEndpoints:
    async def test_requires_super_admin(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
    ) -> None:
        r = await client.get("/api/admin/global-skills", headers=admin_headers)
        assert r.status_code == 403

    async def test_global_skill_assignments_drive_sandbox_projection(
        self,
        client: AsyncClient,
        super_admin_headers: dict[str, str],
    ) -> None:
        sandbox_ids: list[str] = []
        for name in ("global-skills-a", "global-skills-b"):
            r = await client.post(
                "/api/admin/sandboxes",
                json={"name": name, "runtime": "compose", "image": "cappy/sandbox:latest"},
                headers=super_admin_headers,
            )
            assert r.status_code == 201
            sandbox_ids.append(r.json()["id"])

        r = await client.post(
            "/api/admin/global-skills",
            json={
                "name": "python-style",
                "description": "Padrao Python",
                "content": "# Python\n- use snake_case",
                "enabled": True,
                "sandbox_ids": sandbox_ids,
            },
            headers=super_admin_headers,
        )
        assert r.status_code == 201
        skill = r.json()
        assert skill["name"] == "python-style"
        assert set(skill["sandbox_ids"]) == set(sandbox_ids)

        r = await client.get("/api/admin/global-skills", headers=super_admin_headers)
        assert r.status_code == 200
        assert [item["name"] for item in r.json()] == ["python-style"]

        r = await client.get(
            f"/api/admin/sandboxes/{sandbox_ids[0]}/skills",
            headers=super_admin_headers,
        )
        assert r.status_code == 200
        assert [item["name"] for item in r.json()] == ["python-style"]

        r = await client.put(
            f"/api/admin/global-skills/{skill['id']}",
            json={
                "name": "python-style",
                "description": "Atualizado",
                "content": "# Python v2",
                "enabled": False,
                "sandbox_ids": [sandbox_ids[1]],
            },
            headers=super_admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["enabled"] is False
        assert r.json()["sandbox_ids"] == [sandbox_ids[1]]

        r = await client.get(
            f"/api/admin/sandboxes/{sandbox_ids[0]}/skills",
            headers=super_admin_headers,
        )
        assert r.status_code == 200
        assert r.json() == []

        r = await client.get(
            f"/api/admin/sandboxes/{sandbox_ids[1]}/skills",
            headers=super_admin_headers,
        )
        assert r.status_code == 200
        assert [item["enabled"] for item in r.json()] == [False]

        r = await client.delete(
            f"/api/admin/global-skills/{skill['id']}",
            headers=super_admin_headers,
        )
        assert r.status_code == 204


class TestAdminSandboxAgentsEndpoints:
    async def test_requires_admin(self, client: AsyncClient, user_headers: dict[str, str]) -> None:
        sb_id = uuid.uuid4()
        r = await client.get(f"/api/admin/sandboxes/{sb_id}/agents", headers=user_headers)
        assert r.status_code == 403

    async def test_full_crud_lifecycle(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
    ) -> None:
        r = await client.post(
            "/api/admin/sandboxes",
            json={"name": "ag-test", "runtime": "compose", "image": "cappy/sandbox:latest"},
            headers=admin_headers,
        )
        sb_id = r.json()["id"]

        r = await client.post(
            f"/api/admin/sandboxes/{sb_id}/agents",
            json={
                "name": "reviewer",
                "description": "Revisor crítico de PRs.",
                "system_prompt": "Você é um revisor.",
                "model": "claude-sonnet-4-6",
                "tools": ["Read", "Grep"],
                "enabled": True,
            },
            headers=admin_headers,
        )
        assert r.status_code == 201
        body = r.json()
        assert body["sandbox_id"] == sb_id
        assert body["tools"] == ["Read", "Grep"]
        assert body["model"] == "claude-sonnet-4-6"
        agent_id = body["id"]

        # Update
        r = await client.put(
            f"/api/admin/sandboxes/{sb_id}/agents/{agent_id}",
            json={
                "name": "reviewer",
                "description": "atualizado",
                "system_prompt": "v2",
                "model": "claude-opus-4-7",
                "tools": ["Read"],
                "enabled": False,
            },
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["model"] == "claude-opus-4-7"
        assert r.json()["enabled"] is False

        # Delete
        r = await client.delete(
            f"/api/admin/sandboxes/{sb_id}/agents/{agent_id}", headers=admin_headers
        )
        assert r.status_code == 204

    async def test_boot_writes_skills_and_agents_to_bootstrap(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        super_admin_headers: dict[str, str],
        sandbox_bootstrap: FakeSandboxBootstrap,
    ) -> None:
        r = await client.post(
            "/api/admin/sandboxes",
            json={"name": "boot-skag", "runtime": "compose", "image": "cappy/sandbox:latest"},
            headers=admin_headers,
        )
        sb_id = r.json()["id"]

        await client.post(
            f"/api/admin/sandboxes/{sb_id}/skills",
            json={"name": "intro", "content": "# Intro"},
            headers=super_admin_headers,
        )
        await client.post(
            f"/api/admin/sandboxes/{sb_id}/agents",
            json={
                "name": "helper",
                "system_prompt": "Você ajuda.",
                "model": "claude-haiku-4-5",
                "tools": ["Read"],
            },
            headers=admin_headers,
        )

        r = await client.post(f"/api/admin/sandboxes/{sb_id}/boot", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["container_status"] == "configured"

        # Bootstrap recebeu skill + agent:
        assert len(sandbox_bootstrap.skill_calls) == 1
        _, skills = sandbox_bootstrap.skill_calls[0]
        assert [s.name for s in skills] == ["intro"]

        assert len(sandbox_bootstrap.agent_calls) == 1
        _, agents = sandbox_bootstrap.agent_calls[0]
        assert [a.name for a in agents] == ["helper"]
        assert agents[0].tools == ["Read"]
