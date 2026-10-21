"""Focused tests for conversation streaming behavior."""

import uuid

import pytest
from app.application.use_cases import conversations as conversations_module
from app.application.use_cases.conversations import CreateConversation, StreamMessage
from app.domain.entities import UserRole
from app.domain.value_objects import PermissionMode

from tests.conftest import (
    FakeAgent,
    InMemoryConversationRepository,
    InMemoryMessageRepository,
)
from tests.unit.use_cases.streaming_fakes import (
    _CapturingAgent,
    _FakeModelAccessPolicy,
    _SlowAgent,
)


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
        conv.id, user_id, "Ola agente"
    )

    first = await anext(stream)
    second = await anext(stream)
    await stream.aclose()

    assert first.startswith(b": stream-open")
    assert b'"type": "status"' in second
    assert "Conexão com o agente aberta.".encode() in second
    assert b'"stage"' not in second


async def test_sends_heartbeat_while_waiting_for_agent_chunk(
    monkeypatch: pytest.MonkeyPatch,
    conv_repo: InMemoryConversationRepository,
    msg_repo: InMemoryMessageRepository,
    user_id: uuid.UUID,
) -> None:
    monkeypatch.setattr(conversations_module, "_SSE_HEARTBEAT_INTERVAL_S", 0.01)
    conv = await CreateConversation(conv_repo).execute(user_id, "Chat")
    stream = await StreamMessage(conv_repo, msg_repo, _SlowAgent(delay_s=0.05)).execute(
        conv.id, user_id, "Ola agente"
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
        "Ola agente",
        user_role=UserRole.USER,
        override_model="anthropic/paid",
    )
    chunks = [c async for c in stream]

    assert chunks
    assert policy.calls == [(user_id, UserRole.USER, "anthropic/paid")]
    assert agent.last_body is not None
    assert agent.last_body["override_model"] == "openrouter/free"


async def test_stream_defaults_permission_mode_to_bypass_permissions(
    conv_repo: InMemoryConversationRepository,
    msg_repo: InMemoryMessageRepository,
    user_id: uuid.UUID,
) -> None:
    conv = await CreateConversation(conv_repo).execute(user_id, "Chat")
    agent = _CapturingAgent()

    stream = await StreamMessage(conv_repo, msg_repo, agent).execute(
        conv.id,
        user_id,
        "Ola agente",
    )
    chunks = [c async for c in stream]
    saved_conv = await conv_repo.get(conv.id, user_id)

    assert chunks
    assert agent.last_body is not None
    assert agent.last_body["permission_mode"] == PermissionMode.BYPASS_PERMISSIONS.value
    assert saved_conv is not None
    assert saved_conv.permission_mode == PermissionMode.BYPASS_PERMISSIONS.value


async def test_stream_persists_and_dispatches_explicit_permission_mode(
    conv_repo: InMemoryConversationRepository,
    msg_repo: InMemoryMessageRepository,
    user_id: uuid.UUID,
) -> None:
    conv = await CreateConversation(conv_repo).execute(user_id, "Chat")
    agent = _CapturingAgent()

    stream = await StreamMessage(conv_repo, msg_repo, agent).execute(
        conv.id,
        user_id,
        "Ola agente",
        permission_mode=PermissionMode.AUTO.value,
    )
    chunks = [c async for c in stream]
    saved_conv = await conv_repo.get(conv.id, user_id)

    assert chunks
    assert agent.last_body is not None
    assert agent.last_body["permission_mode"] == PermissionMode.AUTO.value
    assert saved_conv is not None
    assert saved_conv.permission_mode == PermissionMode.AUTO.value


async def test_stream_uses_persisted_permission_mode_when_omitted(
    conv_repo: InMemoryConversationRepository,
    msg_repo: InMemoryMessageRepository,
    user_id: uuid.UUID,
) -> None:
    conv = await CreateConversation(conv_repo).execute(user_id, "Chat")
    conv.permission_mode = PermissionMode.ACCEPT_EDITS.value
    await conv_repo.update(conv)
    agent = _CapturingAgent()

    stream = await StreamMessage(conv_repo, msg_repo, agent).execute(
        conv.id,
        user_id,
        "Ola agente",
    )
    chunks = [c async for c in stream]

    assert chunks
    assert agent.last_body is not None
    assert agent.last_body["permission_mode"] == PermissionMode.ACCEPT_EDITS.value


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
            "Ola agente",
            user_role=UserRole.USER,
            override_model="anthropic/paid",
        )

    assert await msg_repo.list_by_conversation(conv.id) == []
