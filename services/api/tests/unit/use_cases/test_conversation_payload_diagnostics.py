"""Focused tests for payload diagnostic chat streaming."""

from __future__ import annotations

import json
import uuid
from collections.abc import Generator
from typing import Any

import pytest
from app.application.use_cases.conversations import CreateConversation, StreamMessage

from tests.conftest import (
    FakeAgent,
    InMemoryConversationRepository,
    InMemoryMessageRepository,
)


class _EventAgent(FakeAgent):
    def __init__(self, events: list[dict[str, Any]]) -> None:
        super().__init__()
        self._events = events

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: list[dict[str, Any]],
        body: dict[str, Any],
    ) -> Generator[str]:
        del user_message, model_id, messages, body
        for event in self._events:
            yield f"data: {json.dumps(event)}\n\n"


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def conv_repo() -> InMemoryConversationRepository:
    return InMemoryConversationRepository()


@pytest.fixture
def msg_repo() -> InMemoryMessageRepository:
    return InMemoryMessageRepository()


async def test_payload_diagnostic_event_is_sanitized_emitted_and_persisted(
    conv_repo: InMemoryConversationRepository,
    msg_repo: InMemoryMessageRepository,
    user_id: uuid.UUID,
) -> None:
    conv = await CreateConversation(conv_repo).execute(user_id, "Chat")
    diagnostic = {
        "total_size_bytes": 999999,
        "source": "openclaude",
        "generated_at": "2026-06-17T15:20:00Z",
        "categories": [
            {
                "key": "attachments",
                "label": "/repos/private/file.png",
                "size_bytes": 300,
                "percentage": 1,
                "raw": "secret",
            },
            {"key": "conversation_history", "label": "hidden prompt", "size_bytes": 700},
        ],
    }
    stream = await StreamMessage(
        conv_repo,
        msg_repo,
        _EventAgent(
            [
                {"type": "payload_diagnostic", "diagnostics": diagnostic},
                {"type": "text", "content": "Resposta"},
                {
                    "type": "done",
                    "model_used": "openrouter/test",
                    "prompt_tokens": 10,
                    "completion_tokens": 3,
                },
            ]
        ),
    ).execute(conv.id, user_id, "Olá agente")

    chunks = [c async for c in stream]
    payloads = _json_payloads(chunks)
    emitted = next(p for p in payloads if p["type"] == "payload_diagnostic")
    saved = await msg_repo.list_by_conversation(conv.id)
    assistant = next(m for m in saved if m.role == "assistant")

    assert emitted["diagnostics"]["total_size_bytes"] == 1000
    assert emitted["diagnostics"]["categories"][0] == {
        "key": "conversation_history",
        "label": "Historico da conversa",
        "size_bytes": 700,
        "percentage": 70.0,
    }
    assert emitted["diagnostics"]["categories"][1]["label"] == "Anexos"
    assert assistant.payload_diagnostics == emitted["diagnostics"]
    assert saved[0].role == "user"
    assert saved[0].payload_diagnostics is None
    assert b"secret" not in b"".join(chunks)
    assert b"/repos/private" not in b"".join(chunks)


async def test_done_model_usage_cost_and_payload_diagnostic_are_persisted_together(
    conv_repo: InMemoryConversationRepository,
    msg_repo: InMemoryMessageRepository,
    user_id: uuid.UUID,
) -> None:
    msg_repo.set_pricing("openrouter/test", input_cost=2.0, output_cost=8.0)
    conv = await CreateConversation(conv_repo).execute(user_id, "Chat")
    stream = await StreamMessage(
        conv_repo,
        msg_repo,
        _EventAgent(
            [
                {
                    "type": "payload_diagnostic",
                    "diagnostics": {
                        "total_size_bytes": 10,
                        "categories": [{"key": "runtime_context", "size_bytes": 10}],
                    },
                },
                {"type": "text", "content": "Resposta"},
                {
                    "type": "done",
                    "model_used": "openrouter/test",
                    "prompt_tokens": 1000,
                    "completion_tokens": 500,
                },
            ]
        ),
    ).execute(conv.id, user_id, "Olá agente")

    chunks = [c async for c in stream]
    payloads = _json_payloads(chunks)
    done = next(p for p in payloads if p["type"] == "done")
    saved = await msg_repo.list_by_conversation(conv.id)
    assistant = next(m for m in saved if m.role == "assistant")

    assert done["model_used"] == "openrouter/test"
    assert done["prompt_tokens"] == 1000
    assert done["completion_tokens"] == 500
    assert assistant.model_used == "openrouter/test"
    assert assistant.prompt_tokens == 1000
    assert assistant.completion_tokens == 500
    assert assistant.cost_usd == 0.006
    assert assistant.payload_diagnostics is not None
    assert assistant.payload_diagnostics["categories"][0]["key"] == "runtime_context"


async def test_absent_payload_diagnostic_keeps_message_without_metadata(
    conv_repo: InMemoryConversationRepository,
    msg_repo: InMemoryMessageRepository,
    user_id: uuid.UUID,
) -> None:
    conv = await CreateConversation(conv_repo).execute(user_id, "Chat")
    stream = await StreamMessage(conv_repo, msg_repo, FakeAgent("Resposta")).execute(
        conv.id, user_id, "Olá agente"
    )

    chunks = [c async for c in stream]
    saved = await msg_repo.list_by_conversation(conv.id)

    assert all(p["type"] != "payload_diagnostic" for p in _json_payloads(chunks))
    assert next(m for m in saved if m.role == "assistant").payload_diagnostics is None


async def test_latest_valid_payload_diagnostic_wins(
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
                    "type": "payload_diagnostic",
                    "diagnostics": {
                        "total_size_bytes": 1,
                        "categories": [{"key": "attachments", "size_bytes": 1}],
                    },
                },
                {
                    "type": "payload_diagnostic",
                    "diagnostics": {
                        "total_size_bytes": 4,
                        "categories": [{"key": "runtime_context", "size_bytes": 4}],
                    },
                },
                {"type": "text", "content": "Resposta"},
                {"type": "done"},
            ]
        ),
    ).execute(conv.id, user_id, "Olá agente")

    chunks = [c async for c in stream]
    saved = await msg_repo.list_by_conversation(conv.id)
    assistant = next(m for m in saved if m.role == "assistant")

    assert len([p for p in _json_payloads(chunks) if p["type"] == "payload_diagnostic"]) == 2
    assert assistant.payload_diagnostics is not None
    assert assistant.payload_diagnostics["categories"][0]["key"] == "runtime_context"


async def test_malformed_payload_diagnostic_is_ignored(
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
                    "type": "payload_diagnostic",
                    "diagnostics": {"total_size_bytes": -10, "categories": "bad"},
                },
                {"type": "text", "content": "Resposta"},
                {"type": "done"},
            ]
        ),
    ).execute(conv.id, user_id, "Olá agente")

    chunks = [c async for c in stream]
    saved = await msg_repo.list_by_conversation(conv.id)

    assert all(p["type"] != "payload_diagnostic" for p in _json_payloads(chunks))
    assert next(m for m in saved if m.role == "assistant").payload_diagnostics is None


async def test_unsafe_payload_diagnostic_category_is_reduced_to_other(
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
                    "type": "payload_diagnostic",
                    "diagnostics": {
                        "total_size_bytes": 5,
                        "source": "provider-key-sk-live-secret",
                        "generated_at": "/repos/private/file.py",
                        "categories": [
                            {
                                "key": "/repos/private/file.py",
                                "label": "sk-live-secret",
                                "size_bytes": 5,
                            }
                        ],
                    },
                },
                {"type": "text", "content": "Resposta"},
                {"type": "done"},
            ]
        ),
    ).execute(conv.id, user_id, "Olá agente")

    chunks = [c async for c in stream]
    diagnostic = next(
        p["diagnostics"] for p in _json_payloads(chunks) if p["type"] == "payload_diagnostic"
    )

    assert diagnostic["source"] == "openclaude"
    assert diagnostic["generated_at"] == ""
    assert diagnostic["categories"] == [
        {"key": "other", "label": "Outros", "size_bytes": 5, "percentage": 100.0}
    ]
    assert b"sk-live-secret" not in b"".join(chunks)
    assert b"/repos/private" not in b"".join(chunks)


def _json_payloads(chunks: list[bytes]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for chunk in chunks:
        if not chunk.startswith(b"data: "):
            continue
        payloads.append(json.loads(chunk[6:]))
    return payloads
