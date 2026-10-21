"""Cache read/write tokens reported by the runtime are saved per response."""

import uuid

import pytest
from app.application.use_cases.conversations import CreateConversation, StreamMessage

from tests.conftest import (
    InMemoryConversationRepository,
    InMemoryMessageRepository,
)
from tests.unit.use_cases.streaming_fakes import _EventAgent


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def conv_repo() -> InMemoryConversationRepository:
    return InMemoryConversationRepository()


@pytest.fixture
def msg_repo() -> InMemoryMessageRepository:
    return InMemoryMessageRepository()


async def test_claude_cli_cache_breakdown_is_saved_per_response(
    conv_repo: InMemoryConversationRepository,
    msg_repo: InMemoryMessageRepository,
    user_id: uuid.UUID,
) -> None:
    conv = await CreateConversation(conv_repo).execute(user_id, "Chat")
    stream = await StreamMessage(
        conv_repo,
        msg_repo,
        _EventAgent(
            [
                {"type": "text", "content": "OK"},
                {
                    "type": "done",
                    "model_used": "claude-sonnet-5",
                    "runtime": "claude_cli",
                    "prompt_tokens": 1000,
                    "completion_tokens": 10,
                    "cache_read_tokens": 900,
                    "cache_write_tokens": 0,
                    "cost_usd": 0.01,
                },
            ]
        ),
    ).execute(conv.id, user_id, "Ola")
    [c async for c in stream]
    assistant = next(
        m for m in await msg_repo.list_by_conversation(conv.id) if m.role == "assistant"
    )

    assert assistant.prompt_tokens == 1000
    assert assistant.cache_read_tokens == 900
    # Zero informado é diferente de "não informado".
    assert assistant.cache_write_tokens == 0


async def test_runtime_without_cache_breakdown_saves_null(
    conv_repo: InMemoryConversationRepository,
    msg_repo: InMemoryMessageRepository,
    user_id: uuid.UUID,
) -> None:
    conv = await CreateConversation(conv_repo).execute(user_id, "Chat")
    stream = await StreamMessage(
        conv_repo,
        msg_repo,
        _EventAgent(
            [
                {"type": "text", "content": "OK"},
                {
                    "type": "done",
                    "model_used": "claude-sonnet-5",
                    "prompt_tokens": 1000,
                    "completion_tokens": 10,
                    "cache_read_tokens": -1,
                },
            ]
        ),
    ).execute(conv.id, user_id, "Ola")
    [c async for c in stream]
    assistant = next(
        m for m in await msg_repo.list_by_conversation(conv.id) if m.role == "assistant"
    )

    assert assistant.cache_read_tokens is None
    assert assistant.cache_write_tokens is None
