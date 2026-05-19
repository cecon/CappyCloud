"""Focused tests for conversation streaming behavior."""

import time
import uuid
from collections.abc import Generator
from typing import Any

import pytest
from app.application.use_cases import conversations as conversations_module
from app.application.use_cases.conversations import CreateConversation, StreamMessage
from app.domain.entities import UserRole
from app.ports.user_access import AiModelAccessPolicy

from tests.conftest import (
    FakeAgent,
    InMemoryConversationRepository,
    InMemoryMessageRepository,
)


class _FakeModelAccessPolicy(AiModelAccessPolicy):
    def __init__(self, resolved: str = "openrouter/free", deny: bool = False) -> None:
        self.resolved = resolved
        self.deny = deny
        self.calls: list[tuple[uuid.UUID, UserRole, str | None]] = []

    async def resolve_model_for_user(
        self,
        user_id: uuid.UUID,
        role: UserRole,
        requested_model_id: str | None,
    ) -> str:
        self.calls.append((user_id, role, requested_model_id))
        if self.deny:
            raise PermissionError("Modelo bloqueado")
        return self.resolved


class _CapturingAgent(FakeAgent):
    def __init__(self) -> None:
        super().__init__()
        self.last_body: dict | None = None

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: list[dict[str, Any]],
        body: dict[str, Any],
    ) -> Generator[str]:
        self.last_body = body
        yield from super().pipe(user_message, model_id, messages, body)


class _SlowAgent(FakeAgent):
    def __init__(self, delay_s: float, response: str = FakeAgent.DEFAULT_RESPONSE) -> None:
        super().__init__(response)
        self._delay_s = delay_s

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: list[dict[str, Any]],
        body: dict[str, Any],
    ) -> Generator[str]:
        time.sleep(self._delay_s)
        yield from super().pipe(user_message, model_id, messages, body)


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def conv_repo() -> InMemoryConversationRepository:
    return InMemoryConversationRepository()


@pytest.fixture
def msg_repo() -> InMemoryMessageRepository:
    return InMemoryMessageRepository()


async def test_starts_stream_with_flush_comment(
    conv_repo: InMemoryConversationRepository,
    msg_repo: InMemoryMessageRepository,
    user_id: uuid.UUID,
) -> None:
    conv = await CreateConversation(conv_repo).execute(user_id, "Chat")
    stream = await StreamMessage(conv_repo, msg_repo, FakeAgent()).execute(
        conv.id, user_id, "Olá agente"
    )

    first = await anext(stream)
    second = await anext(stream)
    await stream.aclose()

    assert first.startswith(b": stream-open")
    assert b'"type": "status"' in second
    assert "Conexão com o agente aberta.".encode() in second


async def test_sends_heartbeat_while_waiting_for_agent_chunk(
    monkeypatch: pytest.MonkeyPatch,
    conv_repo: InMemoryConversationRepository,
    msg_repo: InMemoryMessageRepository,
    user_id: uuid.UUID,
) -> None:
    monkeypatch.setattr(conversations_module, "_SSE_HEARTBEAT_INTERVAL_S", 0.01)
    conv = await CreateConversation(conv_repo).execute(user_id, "Chat")
    stream = await StreamMessage(conv_repo, msg_repo, _SlowAgent(delay_s=0.05)).execute(
        conv.id, user_id, "Olá agente"
    )

    chunks = [c async for c in stream]

    assert b": heartbeat\n\n" in chunks


async def test_resolves_effective_model_before_streaming(
    conv_repo: InMemoryConversationRepository,
    msg_repo: InMemoryMessageRepository,
    user_id: uuid.UUID,
) -> None:
    conv = await CreateConversation(conv_repo).execute(user_id, "Chat")
    agent = _CapturingAgent()
    policy = _FakeModelAccessPolicy(resolved="openrouter/free")
    stream = await StreamMessage(conv_repo, msg_repo, agent, model_access=policy).execute(
        conv.id,
        user_id,
        "Olá agente",
        user_role=UserRole.USER,
        override_model="anthropic/paid",
    )
    chunks = [c async for c in stream]

    assert chunks
    assert policy.calls == [(user_id, UserRole.USER, "anthropic/paid")]
    assert agent.last_body is not None
    assert agent.last_body["override_model"] == "openrouter/free"


async def test_blocks_message_when_model_policy_denies(
    conv_repo: InMemoryConversationRepository,
    msg_repo: InMemoryMessageRepository,
    user_id: uuid.UUID,
) -> None:
    conv = await CreateConversation(conv_repo).execute(user_id, "Chat")
    uc = StreamMessage(
        conv_repo,
        msg_repo,
        FakeAgent(),
        model_access=_FakeModelAccessPolicy(deny=True),
    )

    with pytest.raises(PermissionError):
        await uc.execute(
            conv.id,
            user_id,
            "Olá agente",
            user_role=UserRole.USER,
            override_model="anthropic/paid",
        )

    assert await msg_repo.list_by_conversation(conv.id) == []
