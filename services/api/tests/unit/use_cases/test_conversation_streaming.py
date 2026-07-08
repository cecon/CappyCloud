"""Focused tests for conversation streaming behavior."""

import json
import time
import uuid
from collections.abc import Generator
from typing import Any

import pytest
from app.application.use_cases import conversations as conversations_module
from app.application.use_cases.conversations import CreateConversation, StreamMessage
from app.domain.entities import UserRole
from app.domain.value_objects import PermissionMode
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


class _SelectiveModelAccessPolicy(AiModelAccessPolicy):
    def __init__(self, allowed: set[str]) -> None:
        self.allowed = allowed
        self.calls: list[tuple[uuid.UUID, UserRole, str | None]] = []

    async def resolve_model_for_user(
        self,
        user_id: uuid.UUID,
        role: UserRole,
        requested_model_id: str | None,
    ) -> str:
        self.calls.append((user_id, role, requested_model_id))
        if requested_model_id and requested_model_id in self.allowed:
            return requested_model_id
        raise PermissionError("Modelo bloqueado")


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


async def test_stream_defaults_permission_mode_to_request_permissions(
    conv_repo: InMemoryConversationRepository,
    msg_repo: InMemoryMessageRepository,
    user_id: uuid.UUID,
) -> None:
    conv = await CreateConversation(conv_repo).execute(user_id, "Chat")
    agent = _CapturingAgent()

    stream = await StreamMessage(conv_repo, msg_repo, agent).execute(
        conv.id,
        user_id,
        "Olá agente",
    )
    chunks = [c async for c in stream]
    saved_conv = await conv_repo.get(conv.id, user_id)

    assert chunks
    assert agent.last_body is not None
    assert agent.last_body["permission_mode"] == PermissionMode.REQUEST_PERMISSIONS.value
    assert saved_conv is not None
    assert saved_conv.permission_mode == PermissionMode.REQUEST_PERMISSIONS.value


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
        "Olá agente",
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
        "Olá agente",
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
            "Olá agente",
            user_role=UserRole.USER,
            override_model="anthropic/paid",
        )

    assert await msg_repo.list_by_conversation(conv.id) == []


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
        "OlÃ¡ agente",
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
        "OlÃ¡ agente",
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
    ).execute(conv.id, user_id, "Olá agente")

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
    ).execute(conv.id, user_id, "Olá agente")

    chunks = [c async for c in stream]
    payloads = _json_payloads(chunks)
    saved = await msg_repo.list_by_conversation(conv.id)

    assert any(p["type"] == "action_required" for p in payloads)
    assert any(p["type"] == "timeout" for p in payloads)
    assert any(p.get("output") == "stdout preservado" for p in payloads)
    assert len([m for m in saved if m.role == "assistant"]) == 1


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


def _json_payloads(chunks: list[bytes]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for chunk in chunks:
        if not chunk.startswith(b"data: "):
            continue
        payloads.append(json.loads(chunk[6:]))
    return payloads
