"""Focused tests for conversation streaming with runtime model fallback."""

import uuid

import pytest
from app.application.use_cases.conversations import CreateConversation, StreamMessage
from app.domain.entities import UserRole

from tests.conftest import (
    InMemoryConversationRepository,
    InMemoryMessageRepository,
)
from tests.unit.use_cases.streaming_fakes import (
    _EventAgent,
    _json_payloads,
    _SelectiveModelAccessPolicy,
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


async def test_authorized_runtime_fallback_persists_final_model_and_cost(
    conv_repo: InMemoryConversationRepository,
    msg_repo: InMemoryMessageRepository,
    user_id: uuid.UUID,
) -> None:
    msg_repo.set_pricing("openrouter/fallback", input_cost=3.0, output_cost=7.0)
    conv = await CreateConversation(conv_repo).execute(user_id, "Chat")
    stream = await StreamMessage(
        conv_repo,
        msg_repo,
        _EventAgent(
            [
                {"type": "text", "content": "Resposta"},
                {
                    "type": "done",
                    "model_used": "openrouter/fallback",
                    "prompt_tokens": 1000,
                    "completion_tokens": 1000,
                    "fallback": {
                        "selected_model": "openrouter/selected",
                        "final_model": "openrouter/fallback",
                        "reason": "rate_limit",
                    },
                },
            ]
        ),
        model_access=_SelectiveModelAccessPolicy({"openrouter/selected", "openrouter/fallback"}),
    ).execute(
        conv.id,
        user_id,
        "Ola agente",
        user_role=UserRole.USER,
        override_model="openrouter/selected",
    )

    chunks = [c async for c in stream]
    payloads = _json_payloads(chunks)
    done = next(p for p in payloads if p["type"] == "done")
    assistant = next(
        m for m in await msg_repo.list_by_conversation(conv.id) if m.role == "assistant"
    )

    assert done["model_used"] == "openrouter/fallback"
    assert done["fallback"]["reason"] == "rate_limit"
    assert assistant.model_used == "openrouter/fallback"
    assert assistant.cost_usd == 0.01


async def test_unauthorized_runtime_fallback_is_blocked(
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
                {"type": "text", "content": "Resposta nao autorizada"},
                {
                    "type": "done",
                    "model_used": "openrouter/fallback",
                    "prompt_tokens": 1000,
                    "completion_tokens": 1000,
                },
            ]
        ),
        model_access=_SelectiveModelAccessPolicy({"openrouter/selected"}),
    ).execute(
        conv.id,
        user_id,
        "Ola agente",
        user_role=UserRole.USER,
        override_model="openrouter/selected",
    )

    chunks = [c async for c in stream]
    payloads = _json_payloads(chunks)
    error = next(p for p in payloads if p["type"] == "error")
    assistant = next(
        m for m in await msg_repo.list_by_conversation(conv.id) if m.role == "assistant"
    )

    assert "fallback nao autorizado" in error["message"]
    assert "Resposta nao autorizada" not in assistant.content
    assert assistant.model_used is None


async def test_claude_cli_model_is_not_treated_as_unauthorized_fallback(
    conv_repo: InMemoryConversationRepository,
    msg_repo: InMemoryMessageRepository,
    user_id: uuid.UUID,
) -> None:
    """Claude CLI responde com o modelo da assinatura (`claude login`), não o do catálogo."""
    conv = await CreateConversation(conv_repo).execute(user_id, "Chat")
    stream = await StreamMessage(
        conv_repo,
        msg_repo,
        _EventAgent(
            [
                {"type": "text", "content": "Resposta do Claude CLI"},
                {
                    "type": "done",
                    "model_used": "claude-sonnet-5",
                    "runtime": "claude_cli",
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                },
            ]
        ),
        model_access=_SelectiveModelAccessPolicy({"openrouter/selected"}),
    ).execute(
        conv.id,
        user_id,
        "Ola agente",
        user_role=UserRole.USER,
        override_model="openrouter/selected",
    )

    payloads = _json_payloads([c async for c in stream])
    assistant = next(
        m for m in await msg_repo.list_by_conversation(conv.id) if m.role == "assistant"
    )

    assert not any(p["type"] == "error" for p in payloads)
    assert next(p for p in payloads if p["type"] == "done")["model_used"] == "claude-sonnet-5"
    assert "Resposta do Claude CLI" in assistant.content


async def test_claude_cli_model_skips_catalog_check(
    conv_repo: InMemoryConversationRepository,
    msg_repo: InMemoryMessageRepository,
    user_id: uuid.UUID,
) -> None:
    """``model_from_runtime``: a rota já validou a sandbox; o catálogo nem é consultado."""
    conv = await CreateConversation(conv_repo).execute(user_id, "Chat")
    agent = _EventAgent(
        [
            {"type": "text", "content": "Oi"},
            {"type": "done", "model_used": "claude-opus-4-7", "runtime": "claude_cli"},
        ]
    )
    stream = await StreamMessage(
        conv_repo,
        msg_repo,
        agent,
        model_access=_SelectiveModelAccessPolicy({"openrouter/selected"}),
    ).execute(
        conv.id,
        user_id,
        "Ola",
        user_role=UserRole.USER,
        override_model="claude-cli/opus",
        model_from_runtime=True,
    )

    payloads = _json_payloads([c async for c in stream])

    assert not any(p["type"] == "error" for p in payloads)
    assert next(p for p in payloads if p["type"] == "done")["model_used"] == "claude-opus-4-7"


async def test_claude_cli_plan_usage_is_streamed_and_saved(
    conv_repo: InMemoryConversationRepository,
    msg_repo: InMemoryMessageRepository,
    user_id: uuid.UUID,
) -> None:
    plan = {"five_hour": {"used_pct": 12.0, "resets_at": "2026-09-24T14:30:00.000Z"}}
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
                    "cost_usd": 0.5432,
                    "plan_usage": plan,
                },
            ]
        ),
    ).execute(conv.id, user_id, "Ola")

    payloads = _json_payloads([c async for c in stream])
    assistant = next(
        m for m in await msg_repo.list_by_conversation(conv.id) if m.role == "assistant"
    )

    assert next(p for p in payloads if p["type"] == "done")["plan_usage"] == plan
    assert assistant.plan_usage == plan
    # Custo equivalente pela tabela da API, informado pelo Claude Code (fora do catálogo).
    assert assistant.cost_usd == 0.5432
