"""Shared fixtures and in-memory fakes for all test layers.

In-memory fakes implement the same ABCs as real adapters, proving LSP:
if use cases work with fakes they work with any conforming implementation.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Generator
from typing import Any

import pytest
from app.domain.entities import Conversation, Message, Repository, User, UserRole
from app.ports.agent import AgentPort
from app.ports.repositories import (
    ConversationRepository,
    MessageRepository,
    RepositoryRepository,
    UserRepository,
)
from app.ports.services import PasswordService, TokenService

from .fakes_access import (  # noqa: F401
    InMemoryUserAiModelAccessRepository,
    InMemoryUserRepositoryAccessRepository,
    InMemoryUserSandboxAccessRepository,
)

# Re-export dos fakes de anexos (definidos em ``fakes_attachments.py``) para
# que testes existentes continuem a importar daqui.
from .fakes_attachments import (  # noqa: F401
    FakeVisionDescriber,
    InMemoryAiModelCapabilityLookup,
    InMemoryAttachmentRepository,
    InMemoryAttachmentStorage,
)

# Re-export dos fakes de sandbox/MCP/skills/agents (definidos em
# ``fakes_sandbox.py``) — mesmo objetivo: limitar tamanho do conftest.
from .fakes_sandbox import (  # noqa: F401
    FakeRuntimeGateway,
    FakeSandboxBootstrap,
    InMemoryMcpRepository,
    InMemorySandboxAgentRepository,
    InMemorySandboxRepository,
    InMemorySandboxSkillRepository,
    InMemoryUserMcpServerRepository,
)

# ---------------------------------------------------------------------------
# In-Memory Repository Fakes
# ---------------------------------------------------------------------------


class InMemoryUserRepository(UserRepository):
    """Thread-safe in-memory user store for testing."""

    def __init__(self) -> None:
        self._store: dict[uuid.UUID, User] = {}

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self._store.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        return next((u for u in self._store.values() if u.email == email), None)

    async def save(self, user: User) -> User:
        self._store[user.id] = user
        return user

    async def list_all(self) -> list[User]:
        return sorted(self._store.values(), key=lambda u: u.created_at)

    async def update_role(self, user_id: uuid.UUID, role: UserRole) -> User | None:
        current = self._store.get(user_id)
        if current is None:
            return None
        from dataclasses import replace

        updated = replace(current, role=role)
        self._store[user_id] = updated
        return updated

    async def update_password(
        self,
        user_id: uuid.UUID,
        hashed_password: str,
        *,
        must_change_password: bool,
    ) -> User | None:
        current = self._store.get(user_id)
        if current is None:
            return None
        from dataclasses import replace

        updated = replace(
            current,
            hashed_password=hashed_password,
            must_change_password=must_change_password,
        )
        self._store[user_id] = updated
        return updated


class InMemoryConversationRepository(ConversationRepository):
    """In-memory conversation store for testing."""

    def __init__(self) -> None:
        self._store: dict[uuid.UUID, Conversation] = {}

    async def list_by_user(self, user_id: uuid.UUID) -> list[Conversation]:
        return sorted(
            [c for c in self._store.values() if c.user_id == user_id],
            key=lambda c: c.updated_at,
            reverse=True,
        )

    async def get(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> Conversation | None:
        conv = self._store.get(conversation_id)
        if conv and conv.user_id == user_id:
            return conv
        return None

    async def save(self, conversation: Conversation) -> Conversation:
        self._store[conversation.id] = conversation
        return conversation

    async def update(self, conversation: Conversation) -> Conversation:
        self._store[conversation.id] = conversation
        return conversation


class InMemoryRepositoryRepository(RepositoryRepository):
    """In-memory repository catalog for testing."""

    def __init__(self) -> None:
        self._store: dict[uuid.UUID, Repository] = {}

    async def get(self, repo_id: uuid.UUID) -> Repository | None:
        return self._store.get(repo_id)

    async def get_by_slug(self, slug: str) -> Repository | None:
        return next((r for r in self._store.values() if r.slug == slug), None)

    async def get_authenticated_clone_url(self, repo_id: uuid.UUID) -> str | None:
        repo = self._store.get(repo_id)
        if not repo:
            return None
        # Simula injeção de PAT — devolve URL distinta da bruta, para que
        # testes consigam afirmar que o caller usou a versão autenticada.
        return f"https://pat:fake-token@{repo.clone_url.removeprefix('https://')}"

    async def get_confluence_settings(self, repo_id: uuid.UUID) -> tuple[str, str, list[str]]:
        repo = self._store.get(repo_id)
        if not repo:
            return ("", "", [])
        return (repo.confluence_url, repo.confluence_space, list(repo.confluence_labels))

    def add(self, repo: Repository) -> None:
        """T\u00e9cnica de teste: insere reposit\u00f3rio diretamente sem rota HTTP."""
        self._store[repo.id] = repo


class InMemoryMessageRepository(MessageRepository):
    """In-memory message store for testing."""

    def __init__(self) -> None:
        self._store: list[Message] = []
        # model_id → (input_cost_per_1m_usd, output_cost_per_1m_usd)
        self._pricing: dict[str, tuple[float, float]] = {}

    async def list_by_conversation(self, conversation_id: uuid.UUID) -> list[Message]:
        return sorted(
            [m for m in self._store if m.conversation_id == conversation_id],
            key=lambda m: m.created_at,
        )

    async def save(self, message: Message) -> Message:
        self._store.append(message)
        return message

    async def get_model_pricing(self, model_used: str) -> tuple[float, float] | None:
        return self._pricing.get(model_used)

    def set_pricing(self, model_used: str, input_cost: float, output_cost: float) -> None:
        """Técnica de teste: configura preço de um modelo no fake."""
        self._pricing[model_used] = (input_cost, output_cost)


# ---------------------------------------------------------------------------
# Service Fakes
# ---------------------------------------------------------------------------


class FakePasswordService(PasswordService):
    """Deterministic password service for tests (not cryptographically secure)."""

    def hash(self, plain: str) -> str:
        return f"hashed:{plain}"

    def verify(self, plain: str, hashed: str) -> bool:
        return hashed == f"hashed:{plain}"


class FakeTokenService(TokenService):
    """Deterministic token service for tests."""

    def create(self, subject: str) -> str:
        return f"token:{subject}"

    def decode(self, token: str) -> dict[str, Any]:
        if not token.startswith("token:"):
            raise ValueError("Token inválido")
        return {"sub": token[6:]}


# ---------------------------------------------------------------------------
# Agent Fake
# ---------------------------------------------------------------------------


class FakeAgent(AgentPort):
    """Fake agent that yields a pre-baked SSE text response."""

    DEFAULT_RESPONSE = "Resposta do agente de teste"

    def __init__(self, response: str = DEFAULT_RESPONSE) -> None:
        self._response = response

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: list[dict],  # type: ignore[type-arg]
        body: dict,  # type: ignore[type-arg]
    ) -> Generator[str]:
        payload = json.dumps({"type": "text", "content": self._response})
        yield f"data: {payload}\n\n"
        done = json.dumps({"type": "done"})
        yield f"data: {done}\n\n"

    async def dispatch(  # type: ignore[override]
        self,
        prompt: str,
        env_slug: str = "default",
        conversation_id: Any = None,
        triggered_by: str = "system",
        trigger_payload: Any = None,
        base_branch: str = "",
    ) -> str:
        return str(uuid.uuid4())

    async def on_startup(self) -> None:
        pass

    async def on_shutdown(self) -> None:
        pass

    def cancel_conversation(self, conversation_id: str) -> bool:
        return False


# ---------------------------------------------------------------------------
# Pytest Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user_repo() -> InMemoryUserRepository:
    return InMemoryUserRepository()


@pytest.fixture
def conv_repo() -> InMemoryConversationRepository:
    return InMemoryConversationRepository()


@pytest.fixture
def repository_repo() -> InMemoryRepositoryRepository:
    return InMemoryRepositoryRepository()


@pytest.fixture
def msg_repo() -> InMemoryMessageRepository:
    return InMemoryMessageRepository()


@pytest.fixture
def password_svc() -> FakePasswordService:
    return FakePasswordService()


@pytest.fixture
def token_svc() -> FakeTokenService:
    return FakeTokenService()


@pytest.fixture
def agent() -> FakeAgent:
    return FakeAgent()


@pytest.fixture
def sample_user(user_repo: InMemoryUserRepository) -> User:
    """Pre-created user available in the in-memory repo."""
    import asyncio

    user = User(
        id=uuid.uuid4(),
        email="fixture@test.com",
        hashed_password="hashed:fixture_password",
    )
    asyncio.get_event_loop().run_until_complete(user_repo.save(user))
    return user
