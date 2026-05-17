"""Integration tests — full HTTP stack with dependency_overrides.

Uses httpx.AsyncClient against the real FastAPI app, but with all
external dependencies replaced by in-memory fakes. No DB or network required.
"""

from __future__ import annotations

import uuid

import pytest
from app.adapters.primary.http.admin_sandboxes import (
    get_runtime_gateways,
    get_sandbox_repo,
)
from app.adapters.primary.http.deps import (
    get_agent,
    get_conv_repo,
    get_msg_repo,
    get_password_service,
    get_token_service,
    get_user_repo,
)
from app.domain.entities import ContainerStatus, SandboxRuntime, User, UserRole
from app.main import app
from app.ports.sandbox_runtime import RuntimeProbe, SandboxRuntimeGateway
from httpx import ASGITransport, AsyncClient

from tests.conftest import (
    FakeAgent,
    FakePasswordService,
    FakeTokenService,
    InMemoryConversationRepository,
    InMemoryMessageRepository,
    InMemorySandboxRepository,
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
async def client(
    user_repo: InMemoryUserRepository, sandbox_repo: InMemorySandboxRepository
) -> AsyncClient:
    """HTTP client with all external dependencies replaced by in-memory fakes."""
    conv_repo = InMemoryConversationRepository()
    msg_repo = InMemoryMessageRepository()
    runtimes: dict[SandboxRuntime, SandboxRuntimeGateway] = {
        SandboxRuntime.COMPOSE: _StubRuntimeGateway(),
    }

    app.dependency_overrides[get_user_repo] = lambda: user_repo
    app.dependency_overrides[get_conv_repo] = lambda: conv_repo
    app.dependency_overrides[get_msg_repo] = lambda: msg_repo
    app.dependency_overrides[get_password_service] = lambda: FakePasswordService()
    app.dependency_overrides[get_token_service] = lambda: FakeTokenService()
    app.dependency_overrides[get_agent] = lambda: FakeAgent()
    app.dependency_overrides[get_sandbox_repo] = lambda: sandbox_repo
    app.dependency_overrides[get_runtime_gateways] = lambda: runtimes

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
