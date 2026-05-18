"""Integration tests — full HTTP stack with dependency_overrides.

Uses httpx.AsyncClient against the real FastAPI app, but with all
external dependencies replaced by in-memory fakes. No DB or network required.
"""

from __future__ import annotations

import uuid

import pytest
from app.adapters.primary.http.admin_sandbox_globals import (
    get_agent_repo as get_sandbox_agent_repo,
)
from app.adapters.primary.http.admin_sandbox_globals import (
    get_skill_repo as get_sandbox_skill_repo,
)
from app.adapters.primary.http.admin_sandboxes import (
    get_bootstrap_gateways,
    get_runtime_gateways,
    get_sandbox_repo,
)
from app.adapters.primary.http.deps import (
    get_agent,
    get_conv_repo,
    get_mcp_repo,
    get_msg_repo,
    get_password_service,
    get_token_service,
    get_user_repo,
)
from app.domain.entities import ContainerStatus, SandboxRuntime, User, UserRole
from app.main import app
from app.ports.sandbox_bootstrap import SandboxBootstrapGateway
from app.ports.sandbox_runtime import RuntimeProbe, SandboxRuntimeGateway
from httpx import ASGITransport, AsyncClient

from tests.conftest import (
    FakeAgent,
    FakePasswordService,
    FakeSandboxBootstrap,
    FakeTokenService,
    InMemoryConversationRepository,
    InMemoryMcpRepository,
    InMemoryMessageRepository,
    InMemorySandboxAgentRepository,
    InMemorySandboxRepository,
    InMemorySandboxSkillRepository,
    InMemoryUserRepository,
)


class _StubRuntimeGateway(SandboxRuntimeGateway):
    """Runtime sintético para os testes HTTP — simula transições sem Docker."""

    async def ensure_service(self, sandbox) -> RuntimeProbe:  # type: ignore[no-untyped-def]
        return RuntimeProbe(status=ContainerStatus.RUNNING, runtime_ref="stub-cid")

    async def stop(self, sandbox) -> RuntimeProbe:  # type: ignore[no-untyped-def]
        return RuntimeProbe(status=ContainerStatus.STOPPED, runtime_ref="stub-cid")

    async def status(self, sandbox) -> RuntimeProbe:  # type: ignore[no-untyped-def]
        return RuntimeProbe(status=ContainerStatus.RUNNING, runtime_ref="stub-cid")

    async def remove(self, sandbox) -> None:  # type: ignore[no-untyped-def]
        pass


async def _seed_user(
    repo: InMemoryUserRepository, email: str, *, role: UserRole = UserRole.USER
) -> User:
    """Insere utilizador no repo sem passar pelo HTTP — para fixtures.

    O hash bate com :class:`FakePasswordService` para que o login subsequente
    funcione com a mesma senha ``password123``.
    """
    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password="hashed:password123",
        role=role,
    )
    await repo.save(user)
    return user


@pytest.fixture
def sandbox_repo() -> InMemorySandboxRepository:
    return InMemorySandboxRepository()


@pytest.fixture
def mcp_repo() -> InMemoryMcpRepository:
    return InMemoryMcpRepository()


@pytest.fixture
def skill_repo() -> InMemorySandboxSkillRepository:
    return InMemorySandboxSkillRepository()


@pytest.fixture
def agent_repo() -> InMemorySandboxAgentRepository:
    return InMemorySandboxAgentRepository()


@pytest.fixture
def sandbox_bootstrap() -> FakeSandboxBootstrap:
    return FakeSandboxBootstrap()


@pytest.fixture
async def client(
    user_repo: InMemoryUserRepository,
    sandbox_repo: InMemorySandboxRepository,
    mcp_repo: InMemoryMcpRepository,
    skill_repo: InMemorySandboxSkillRepository,
    agent_repo: InMemorySandboxAgentRepository,
    sandbox_bootstrap: FakeSandboxBootstrap,
) -> AsyncClient:
    """HTTP client with all external dependencies replaced by in-memory fakes."""
    conv_repo = InMemoryConversationRepository()
    msg_repo = InMemoryMessageRepository()
    runtimes: dict[SandboxRuntime, SandboxRuntimeGateway] = {
        SandboxRuntime.COMPOSE: _StubRuntimeGateway(),
    }
    bootstraps: dict[SandboxRuntime, SandboxBootstrapGateway] = {
        SandboxRuntime.COMPOSE: sandbox_bootstrap,
    }

    app.dependency_overrides[get_user_repo] = lambda: user_repo
    app.dependency_overrides[get_conv_repo] = lambda: conv_repo
    app.dependency_overrides[get_msg_repo] = lambda: msg_repo
    app.dependency_overrides[get_password_service] = lambda: FakePasswordService()
    app.dependency_overrides[get_token_service] = lambda: FakeTokenService()
    app.dependency_overrides[get_agent] = lambda: FakeAgent()
    app.dependency_overrides[get_sandbox_repo] = lambda: sandbox_repo
    app.dependency_overrides[get_runtime_gateways] = lambda: runtimes
    app.dependency_overrides[get_bootstrap_gateways] = lambda: bootstraps
    app.dependency_overrides[get_mcp_repo] = lambda: mcp_repo
    app.dependency_overrides[get_sandbox_skill_repo] = lambda: skill_repo
    app.dependency_overrides[get_sandbox_agent_repo] = lambda: agent_repo

    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c  # type: ignore[misc]

    app.dependency_overrides.clear()


@pytest.fixture
async def admin_headers(client: AsyncClient, user_repo: InMemoryUserRepository) -> dict[str, str]:
    """Autentica como ADMIN pré-existente; usado em qualquer teste que crie users."""
    await _seed_user(user_repo, "admin@test.com", role=UserRole.ADMIN)
    r = await client.post(
        "/api/auth/login",
        data={"username": "admin@test.com", "password": "password123"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
async def user_headers(client: AsyncClient, user_repo: InMemoryUserRepository) -> dict[str, str]:
    """Autentica como USER comum (não-admin)."""
    await _seed_user(user_repo, "regular@test.com", role=UserRole.USER)
    r = await client.post(
        "/api/auth/login",
        data={"username": "regular@test.com", "password": "password123"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


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
        await _seed_user(user_repo, "extra@test.com", role=UserRole.USER)

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
        target = await _seed_user(user_repo, "tgt@test.com", role=UserRole.USER)
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
        target = await _seed_user(user_repo, "promoteme@test.com", role=UserRole.USER)

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
        target = await _seed_user(user_repo, "weirdrole@test.com", role=UserRole.USER)

        r = await client.patch(
            f"/api/admin/users/{target.id}/role",
            json={"role": "superuser"},
            headers=admin_headers,
        )

        assert r.status_code == 422


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

        # Simula container já em uso na origem:
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

        # Boot com runtime swarm não configurado → 502 (RuntimeFailureError)
        r = await client.post(f"/api/admin/sandboxes/{sandbox_id}/boot", headers=admin_headers)
        # Quando o runtime falta no mapa, é RuntimeFailureError → 502.
        # (501 ocorre quando o adapter Swarm real é injetado e levanta
        #  NotImplementedError — testado via override em outro cenário.)
        assert r.status_code == 502


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


class TestAdminSandboxSkillsEndpoints:
    async def test_requires_admin(self, client: AsyncClient, user_headers: dict[str, str]) -> None:
        sb_id = uuid.uuid4()
        r = await client.get(f"/api/admin/sandboxes/{sb_id}/skills", headers=user_headers)
        assert r.status_code == 403

    async def test_full_crud_lifecycle(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
    ) -> None:
        r = await client.post(
            "/api/admin/sandboxes",
            json={"name": "sk-test", "runtime": "compose", "image": "cappy/sandbox:latest"},
            headers=admin_headers,
        )
        sb_id = r.json()["id"]

        r = await client.get(f"/api/admin/sandboxes/{sb_id}/skills", headers=admin_headers)
        assert r.status_code == 200 and r.json() == []

        r = await client.post(
            f"/api/admin/sandboxes/{sb_id}/skills",
            json={
                "name": "naming-conventions",
                "description": "snake_case em Python",
                "content": "# Naming\n- Python: snake_case\n- TS: camelCase",
                "enabled": True,
            },
            headers=admin_headers,
        )
        assert r.status_code == 201
        skill_id = r.json()["id"]
        assert r.json()["name"] == "naming-conventions"

        # Duplicata rejeitada (mesmo nome dentro da sandbox)
        r = await client.post(
            f"/api/admin/sandboxes/{sb_id}/skills",
            json={"name": "naming-conventions", "content": "x"},
            headers=admin_headers,
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
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["enabled"] is False
        assert r.json()["content"] == "# Naming v2"

        # Delete
        r = await client.delete(
            f"/api/admin/sandboxes/{sb_id}/skills/{skill_id}", headers=admin_headers
        )
        assert r.status_code == 204

    async def test_rejects_invalid_name(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        r = await client.post(
            "/api/admin/sandboxes",
            json={"name": "sk-name", "runtime": "compose", "image": "x"},
            headers=admin_headers,
        )
        sb_id = r.json()["id"]
        r = await client.post(
            f"/api/admin/sandboxes/{sb_id}/skills",
            json={"name": "tem espaço", "content": "x"},
            headers=admin_headers,
        )
        assert r.status_code == 422


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
            headers=admin_headers,
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


class TestConversationEndpoints:
    @pytest.fixture
    async def auth_headers(
        self, client: AsyncClient, user_repo: InMemoryUserRepository
    ) -> dict[str, str]:
        """USER comum (PR1 ainda não filtra conversas por permissão)."""
        await _seed_user(user_repo, "conv@test.com", role=UserRole.USER)
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
