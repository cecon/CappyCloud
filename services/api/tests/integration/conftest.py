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
from app.adapters.primary.http.admin_user_access import (
    get_ai_model_access_repo,
    get_models_by_tier_lookup,
    get_repository_access_repo,
    get_sandbox_access_repo,
)
from app.adapters.primary.http.deps import (
    get_agent,
    get_ai_model_access_policy,
    get_chat_command_runtime,
    get_conv_repo,
    get_delete_user_workspace_uc,
    get_ensure_user_workspace_uc,
    get_list_user_workspaces_uc,
    get_mcp_repo,
    get_model_profile_lookup,
    get_msg_repo,
    get_password_service,
    get_repository_mcp_tool_gateway,
    get_repository_repo,
    get_sandbox_workspace_gateway,
    get_token_service,
    get_user_mcp_repo,
    get_user_repo,
    get_user_repository_access_repo,
    get_user_workspace_repo,
)
from app.adapters.primary.http.repository_mcp import get_mcp_telemetry_recorder
from app.application.use_cases.admin_user_access import ModelsByTierLookup
from app.application.use_cases.user_workspaces import (
    DeleteUserRepositoryWorkspace,
    EnsureUserRepositoryWorkspace,
    ListUserRepositoryWorkspaces,
)
from app.domain.chat_commands import CommandCategory, CommandExecutionMode, SlashCommand
from app.domain.entities import ContainerStatus, ModelTier, SandboxRuntime, User, UserRole
from app.main import app
from app.ports.model_profiles import AuthorizedModelProfile
from app.ports.repository_mcp import RepositoryMcpToolGateway
from app.ports.sandbox_bootstrap import SandboxBootstrapGateway
from app.ports.sandbox_runtime import RuntimeProbe, SandboxRuntimeGateway
from app.ports.user_access import AiModelAccessPolicy
from httpx import ASGITransport, AsyncClient

from tests.conftest import (
    FakeAgent,
    FakePasswordService,
    FakeSandboxBootstrap,
    FakeSandboxWorkspaceGateway,
    FakeTokenService,
    InMemoryConversationRepository,
    InMemoryMcpRepository,
    InMemoryMessageRepository,
    InMemoryRepositoryRepository,
    InMemorySandboxAgentRepository,
    InMemorySandboxRepository,
    InMemorySandboxSkillRepository,
    InMemoryUserAiModelAccessRepository,
    InMemoryUserMcpServerRepository,
    InMemoryUserRepository,
    InMemoryUserRepositoryAccessRepository,
    InMemoryUserSandboxAccessRepository,
    InMemoryUserWorkspaceRepository,
)
from tests.fakes_chat_commands import FakeChatCommandRuntime, FakeModelProfileLookup


class _StubModelsByTierLookup(ModelsByTierLookup):
    """Lookup sintético para testes — mantém um mapping tier → ids em memória."""

    def __init__(self, mapping: dict[ModelTier, list[uuid.UUID]] | None = None) -> None:
        self._mapping: dict[ModelTier, list[uuid.UUID]] = mapping or {}

    async def list_active_model_ids_by_tier(self, tier: ModelTier) -> list[uuid.UUID]:
        return list(self._mapping.get(tier, []))


class _StubRuntimeGateway(SandboxRuntimeGateway):
    """Runtime sintético para os testes HTTP — simula transições sem Docker."""

    async def ensure_service(self, sandbox, *, restart: bool = False) -> RuntimeProbe:  # type: ignore[no-untyped-def]
        return RuntimeProbe(status=ContainerStatus.RUNNING, runtime_ref="stub-cid")

    async def stop(self, sandbox) -> RuntimeProbe:  # type: ignore[no-untyped-def]
        return RuntimeProbe(status=ContainerStatus.STOPPED, runtime_ref="stub-cid")

    async def status(self, sandbox) -> RuntimeProbe:  # type: ignore[no-untyped-def]
        return RuntimeProbe(status=ContainerStatus.RUNNING, runtime_ref="stub-cid")

    async def remove(self, sandbox) -> None:  # type: ignore[no-untyped-def]
        pass


class _AllowAllAiModelAccessPolicy(AiModelAccessPolicy):
    async def resolve_model_for_user(
        self,
        user_id: uuid.UUID,
        role: UserRole,
        requested_model_id: str | None,
    ) -> str:
        return requested_model_id or "openrouter/free"


class _FakeRepositoryMcpToolGateway(RepositoryMcpToolGateway):
    async def call_tool(self, server, tool_name, arguments):  # type: ignore[no-untyped-def]
        return {
            "tool": tool_name,
            "repository_id": str(server.repository_id),
            "arguments": arguments,
        }


async def seed_user(
    repo: InMemoryUserRepository,
    email: str,
    *,
    role: UserRole = UserRole.USER,
    is_super_admin: bool = False,
    must_change_password: bool = False,
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
        is_super_admin=is_super_admin,
        must_change_password=must_change_password,
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
def user_mcp_repo() -> InMemoryUserMcpServerRepository:
    return InMemoryUserMcpServerRepository()


@pytest.fixture
def repository_repo() -> InMemoryRepositoryRepository:
    return InMemoryRepositoryRepository()


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
def sandbox_access_repo() -> InMemoryUserSandboxAccessRepository:
    return InMemoryUserSandboxAccessRepository()


@pytest.fixture
def repository_access_repo() -> InMemoryUserRepositoryAccessRepository:
    return InMemoryUserRepositoryAccessRepository()


@pytest.fixture
def ai_model_access_repo() -> InMemoryUserAiModelAccessRepository:
    return InMemoryUserAiModelAccessRepository()


@pytest.fixture
def user_workspace_repo() -> InMemoryUserWorkspaceRepository:
    return InMemoryUserWorkspaceRepository()


@pytest.fixture
def sandbox_workspace_gateway() -> FakeSandboxWorkspaceGateway:
    return FakeSandboxWorkspaceGateway()


@pytest.fixture
def models_by_tier_lookup() -> _StubModelsByTierLookup:
    return _StubModelsByTierLookup()


@pytest.fixture
async def client(
    user_repo: InMemoryUserRepository,
    repository_repo: InMemoryRepositoryRepository,
    sandbox_repo: InMemorySandboxRepository,
    mcp_repo: InMemoryMcpRepository,
    user_mcp_repo: InMemoryUserMcpServerRepository,
    skill_repo: InMemorySandboxSkillRepository,
    agent_repo: InMemorySandboxAgentRepository,
    sandbox_bootstrap: FakeSandboxBootstrap,
    sandbox_access_repo: InMemoryUserSandboxAccessRepository,
    repository_access_repo: InMemoryUserRepositoryAccessRepository,
    ai_model_access_repo: InMemoryUserAiModelAccessRepository,
    user_workspace_repo: InMemoryUserWorkspaceRepository,
    sandbox_workspace_gateway: FakeSandboxWorkspaceGateway,
    models_by_tier_lookup: _StubModelsByTierLookup,
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
    app.dependency_overrides[get_repository_repo] = lambda: repository_repo
    app.dependency_overrides[get_password_service] = lambda: FakePasswordService()
    app.dependency_overrides[get_token_service] = lambda: FakeTokenService()
    app.dependency_overrides[get_agent] = lambda: FakeAgent()
    app.dependency_overrides[get_chat_command_runtime] = lambda: FakeChatCommandRuntime(
        [
            SlashCommand(
                name="/ctx",
                description="Ver contexto",
                category=CommandCategory.CONTEXT,
                execution_mode=CommandExecutionMode.CHAT_ACTION,
            )
        ]
    )
    app.dependency_overrides[get_model_profile_lookup] = lambda: FakeModelProfileLookup(
        [
            AuthorizedModelProfile(
                model_id="openrouter/free",
                display_name="Free",
                provider="OpenRouter",
                active=True,
                provider_active=True,
                capabilities=["text"],
                context_window=128000,
            )
        ]
    )
    app.dependency_overrides[get_ai_model_access_policy] = lambda: _AllowAllAiModelAccessPolicy()
    app.dependency_overrides[get_sandbox_repo] = lambda: sandbox_repo
    app.dependency_overrides[get_runtime_gateways] = lambda: runtimes
    app.dependency_overrides[get_bootstrap_gateways] = lambda: bootstraps
    app.dependency_overrides[get_mcp_repo] = lambda: mcp_repo
    app.dependency_overrides[get_user_mcp_repo] = lambda: user_mcp_repo
    app.dependency_overrides[get_repository_mcp_tool_gateway] = lambda: (
        _FakeRepositoryMcpToolGateway()
    )
    app.dependency_overrides[get_mcp_telemetry_recorder] = lambda: lambda record: None
    app.dependency_overrides[get_sandbox_skill_repo] = lambda: skill_repo
    app.dependency_overrides[get_sandbox_agent_repo] = lambda: agent_repo
    app.dependency_overrides[get_sandbox_access_repo] = lambda: sandbox_access_repo
    app.dependency_overrides[get_repository_access_repo] = lambda: repository_access_repo
    app.dependency_overrides[get_user_repository_access_repo] = lambda: repository_access_repo
    app.dependency_overrides[get_ai_model_access_repo] = lambda: ai_model_access_repo
    app.dependency_overrides[get_user_workspace_repo] = lambda: user_workspace_repo
    app.dependency_overrides[get_sandbox_workspace_gateway] = lambda: sandbox_workspace_gateway
    app.dependency_overrides[get_ensure_user_workspace_uc] = lambda: EnsureUserRepositoryWorkspace(
        user_workspace_repo,
        repository_repo,
        repository_access_repo,
        sandbox_workspace_gateway,
    )
    app.dependency_overrides[get_list_user_workspaces_uc] = lambda: ListUserRepositoryWorkspaces(
        user_workspace_repo
    )
    app.dependency_overrides[get_delete_user_workspace_uc] = lambda: DeleteUserRepositoryWorkspace(
        user_workspace_repo, sandbox_workspace_gateway
    )
    app.dependency_overrides[get_models_by_tier_lookup] = lambda: models_by_tier_lookup

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
async def super_admin_headers(
    client: AsyncClient, user_repo: InMemoryUserRepository
) -> dict[str, str]:
    """Autentica como ADMIN marcado como super admin."""
    await seed_user(
        user_repo,
        "superadmin@test.com",
        role=UserRole.ADMIN,
        is_super_admin=True,
    )
    r = await client.post(
        "/api/auth/login",
        data={"username": "superadmin@test.com", "password": "password123"},
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
