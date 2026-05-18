"""Integration HTTP — /api/admin/sandboxes/{id}/mcps (ADR-004 §6)."""

from __future__ import annotations

import uuid

from httpx import AsyncClient

from tests.conftest import FakeSandboxBootstrap


class TestAdminSandboxMcpsEndpoints:
    async def test_requires_admin(self, client: AsyncClient, user_headers: dict[str, str]) -> None:
        sb_id = uuid.uuid4()
        r = await client.get(f"/api/admin/sandboxes/{sb_id}/mcps", headers=user_headers)
        assert r.status_code == 403

    async def test_full_crud_lifecycle(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
    ) -> None:
        # 1. Cria sandbox base
        r = await client.post(
            "/api/admin/sandboxes",
            json={
                "name": "mcp-test",
                "runtime": "compose",
                "image": "cappy/sandbox:latest",
            },
            headers=admin_headers,
        )
        assert r.status_code == 201
        sb_id = r.json()["id"]

        # 2. Lista vazia
        r = await client.get(f"/api/admin/sandboxes/{sb_id}/mcps", headers=admin_headers)
        assert r.status_code == 200 and r.json() == []

        # 3. Cria MCP
        r = await client.post(
            f"/api/admin/sandboxes/{sb_id}/mcps",
            json={
                "name": "github",
                "command": "npx",
                "args": ["-y", "@mcp/github"],
                "env": {"GITHUB_TOKEN": "x"},
                "enabled": True,
            },
            headers=admin_headers,
        )
        assert r.status_code == 201
        mcp_id = r.json()["id"]
        assert r.json()["sandbox_id"] == sb_id

        # 4. Duplicata rejeitada (mesmo nome dentro da sandbox)
        r = await client.post(
            f"/api/admin/sandboxes/{sb_id}/mcps",
            json={
                "name": "github",
                "command": "npx",
                "args": [],
                "env": {},
                "enabled": True,
            },
            headers=admin_headers,
        )
        assert r.status_code == 409

        # 5. Atualiza
        r = await client.put(
            f"/api/admin/sandboxes/{sb_id}/mcps/{mcp_id}",
            json={
                "name": "github",
                "command": "npx",
                "args": ["-y", "@mcp/github@latest"],
                "env": {"GITHUB_TOKEN": "y"},
                "enabled": False,
            },
            headers=admin_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["enabled"] is False
        assert body["env"]["GITHUB_TOKEN"] == "y"

        # 6. Export — disabled é omitido
        r = await client.get(f"/api/admin/sandboxes/{sb_id}/mcps/export", headers=admin_headers)
        assert r.status_code == 200
        assert r.json() == {"mcpServers": {}}

        # 7. Delete
        r = await client.delete(
            f"/api/admin/sandboxes/{sb_id}/mcps/{mcp_id}", headers=admin_headers
        )
        assert r.status_code == 204

        # 8. Lista volta a vazio
        r = await client.get(f"/api/admin/sandboxes/{sb_id}/mcps", headers=admin_headers)
        assert r.status_code == 200 and r.json() == []

    async def test_boot_triggers_bootstrap_with_mcp_settings(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        sandbox_bootstrap: FakeSandboxBootstrap,
    ) -> None:
        # Cria sandbox + MCP, depois bota → bootstrap escreve settings.json:
        r = await client.post(
            "/api/admin/sandboxes",
            json={
                "name": "boot-mcp",
                "runtime": "compose",
                "image": "cappy/sandbox:latest",
            },
            headers=admin_headers,
        )
        sb_id = r.json()["id"]

        r = await client.post(
            f"/api/admin/sandboxes/{sb_id}/mcps",
            json={
                "name": "fs",
                "command": "uvx",
                "args": ["mcp-server-filesystem", "/repos"],
                "env": {},
                "enabled": True,
            },
            headers=admin_headers,
        )
        assert r.status_code == 201

        r = await client.post(f"/api/admin/sandboxes/{sb_id}/boot", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["container_status"] == "configured"

        # Bootstrap foi chamado com o settings.json correto:
        assert len(sandbox_bootstrap.calls) == 1
        _, settings = sandbox_bootstrap.calls[0]
        assert settings["mcpServers"]["fs"]["command"] == "uvx"
        assert settings["mcpServers"]["fs"]["args"] == [
            "mcp-server-filesystem",
            "/repos",
        ]
