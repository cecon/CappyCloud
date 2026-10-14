"""Focused tests for conversation streaming event pass-through and persistence."""

import json
import uuid
from types import SimpleNamespace

import pytest
from app.application.use_cases.conversations import CreateConversation, StreamMessage

from tests.conftest import (
    FakeAgent,
    InMemoryConversationRepository,
    InMemoryMessageRepository,
)
from tests.unit.agent_runtime_test_loader import grpc_event_handlers as grpc_handlers
from tests.unit.use_cases.streaming_fakes import (
    _EventAgent,
    _json_payloads,
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


async def test_error_event_saves_single_assistant_error_message(
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
                {"type": "error", "message": "timeout"},
                {"type": "done"},
            ]
        ),
    ).execute(conv.id, user_id, "Ola agente")

    chunks = [c async for c in stream]
    saved = await msg_repo.list_by_conversation(conv.id)

    assert any(p["type"] == "error" for p in _json_payloads(chunks))
    assistants = [m for m in saved if m.role == "assistant"]
    assert len(assistants) == 1
    assert assistants[0].content == "**Erro:** timeout"


async def test_action_timeout_done_and_tool_stdout_events_pass_through(
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
                {"type": "action_required", "question": "Continuar?"},
                {"type": "timeout", "message": "silencioso"},
                {
                    "type": "tool_result",
                    "name": "Bash",
                    "output": "stdout preservado",
                    "is_error": True,
                },
                {"type": "text", "content": "Resposta"},
                {"type": "done"},
                {"type": "done"},
            ]
        ),
    ).execute(conv.id, user_id, "Ola agente")

    chunks = [c async for c in stream]
    payloads = _json_payloads(chunks)
    saved = await msg_repo.list_by_conversation(conv.id)

    assert any(p["type"] == "action_required" for p in payloads)
    assert any(p["type"] == "timeout" for p in payloads)
    assert any(p.get("output") == "stdout preservado" for p in payloads)
    assert len([m for m in saved if m.role == "assistant"]) == 1


async def test_context_and_subagent_events_pass_through_without_persistence_side_effects(
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
                {
                    "type": "context_progress",
                    "label": "Contexto usado",
                    "current_value": 10,
                    "limit_value": 100,
                    "percent": 10,
                    "financial": False,
                },
                {
                    "type": "subagent_group",
                    "parent_turn_id": "turn_1",
                    "label": "Auxiliares",
                    "collapsible": True,
                    "activities": [
                        {"id": "agent_1", "name": "repo-a", "state": "done", "detail": "ok"}
                    ],
                },
                {"type": "text", "content": "Resposta"},
                {"type": "done"},
            ]
        ),
    ).execute(conv.id, user_id, "Ola agente")

    payloads = _json_payloads([c async for c in stream])
    saved = await msg_repo.list_by_conversation(conv.id)

    assert any(p["type"] == "context_progress" for p in payloads)
    assert any(p["type"] == "subagent_group" for p in payloads)
    assistants = [m for m in saved if m.role == "assistant"]
    assert len(assistants) == 1
    assert assistants[0].content == "Resposta"


async def test_tool_start_arguments_remain_available_through_stream_done(
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
                {
                    "type": "tool_start",
                    "name": "Bash",
                    "input": '{"command":"npm run lint"}',
                    "id": "toolu_1",
                },
                {"type": "text", "content": "Feito"},
                {"type": "done"},
            ]
        ),
    ).execute(conv.id, user_id, "Rode o lint")

    chunks = [c async for c in stream]
    payloads = _json_payloads(chunks)
    tool_start = next(p for p in payloads if p["type"] == "tool_start")

    assert tool_start["id"] == "toolu_1"
    assert json.loads(tool_start["input"]) == {"command": "npm run lint"}
    assert payloads[-1]["type"] == "done"


async def test_command_events_are_sanitized_and_forwarded(
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
                {
                    "type": "command_start",
                    "command": "/doctor",
                    "label": "Diagnostico api_key=secret",
                },
                {
                    "type": "command_result",
                    "command": "/doctor",
                    "status": "completed",
                    "summary": "OK token: hidden",
                    "details_markdown": "C:\\Users\\cecon\\repo",
                },
                {"type": "done"},
            ]
        ),
    ).execute(conv.id, user_id, "Rode /doctor")

    payloads = _json_payloads([c async for c in stream])
    start = next(p for p in payloads if p["type"] == "command_start")
    result = next(p for p in payloads if p["type"] == "command_result")

    assert start["command"] == "/doctor"
    assert start["label"] == "Diagnostico api_key=***"
    assert result["status"] == "completed"
    assert result["summary"] == "OK token: ***"
    assert result["details_markdown"] == "C:\\Users\\***\\repo"


async def test_cursor_reconnect_does_not_save_duplicate_user_message(
    conv_repo: InMemoryConversationRepository,
    msg_repo: InMemoryMessageRepository,
    user_id: uuid.UUID,
) -> None:
    conv = await CreateConversation(conv_repo).execute(user_id, "Chat")
    await StreamMessage(conv_repo, msg_repo, FakeAgent()).execute(
        conv.id,
        user_id,
        "Ola agente",
    )

    stream = await StreamMessage(conv_repo, msg_repo, FakeAgent()).execute(
        conv.id,
        user_id,
        "Ola agente",
        cursor=42,
    )
    payloads = _json_payloads([c async for c in stream])
    saved = await msg_repo.list_by_conversation(conv.id)

    assert [m.content for m in saved if m.role == "user"] == ["Ola agente"]
    assert payloads[-1]["type"] == "done"


def test_command_stream_event_handlers_sanitize_payloads() -> None:
    start = grpc_handlers.command_start_event(
        SimpleNamespace(command_start=SimpleNamespace(command="/doctor", label="Diagnostico"))
    )
    result = grpc_handlers.command_result_event(
        SimpleNamespace(
            command_result=SimpleNamespace(
                command="/doctor",
                status="completed",
                summary="WebSearch disponivel",
                details_markdown="ok",
            )
        )
    )

    assert start == ("command_start", {"command": "/doctor", "label": "Diagnostico"})
    assert result[0] == "command_result"
    assert result[1]["status"] == "completed"
