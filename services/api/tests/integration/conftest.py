"""Fixtures compartilhadas pelos testes de integração HTTP."""

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


async def seed_user(
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
    await seed_user(user_repo, "admin@test.com", role=UserRole.ADMIN)
    r = await client.post(
        "/api/auth/login",
        data={"username": "admin@test.com", "password": "password123"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
async def user_headers(client: AsyncClient, user_repo: InMemoryUserRepository) -> dict[str, str]:
    """Autentica como USER comum (não-admin)."""
    await seed_user(user_repo, "regular@test.com", role=UserRole.USER)
    r = await client.post(
        "/api/auth/login",
        data={"username": "regular@test.com", "password": "password123"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
