"""Regression tests for CappyCloud agent runtime edge cases."""

from __future__ import annotations

import asyncio
import types
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from .agent_runtime_test_loader import (
    assistant_output as _assistant_output,
)
from .agent_runtime_test_loader import (
    grpc_event_handlers as _grpc_event_handlers,
)
from .agent_runtime_test_loader import (
    pipeline_event_stream as _pipeline_event_stream,
)
from .agent_runtime_test_loader import (
    pipeline_helpers as _pipeline_helpers,
)
from .agent_runtime_test_loader import (
    signoz_context as _signoz_context,
)
from .agent_runtime_test_loader import (
    task_final_message as _task_final_message,
)


async def test_push_mcp_config_reads_enabled_mcps_by_sandbox(monkeypatch) -> None:
    sandbox_id = uuid.uuid4()
    captured: dict[str, Any] = {}

    class FakeConn:
        async def fetch(self, query: str, arg: uuid.UUID) -> list[dict[str, Any]]:
            captured["query"] = query
            captured["arg"] = arg
            return [
                {
                    "name": "github",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "env": {"GITHUB_TOKEN": "token"},
                }
            ]

        async def close(self) -> None:
            captured["closed"] = True

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            pass

        async def post(self, url: str, json: dict) -> types.SimpleNamespace:
            captured["url"] = url
            captured["json"] = json
            return types.SimpleNamespace(status_code=200)

    async def fake_connect(database_url: str) -> FakeConn:
        captured["database_url"] = database_url
        return FakeConn()

    monkeypatch.setattr(_pipeline_helpers.asyncpg, "connect", fake_connect)
    monkeypatch.setattr(_pipeline_helpers.httpx, "AsyncClient", FakeAsyncClient)

    await _pipeline_helpers.push_mcp_config(
        "postgresql://db", str(sandbox_id), "http://sandbox:8080"
    )

    assert "sandbox_id = $1" in captured["query"]
    assert "user_id" not in captured["query"]
    assert captured["arg"] == sandbox_id
    assert captured["url"] == "http://sandbox:8080/mcp/configure"
    assert captured["json"]["mcpServers"]["github"]["command"] == "npx"
    assert captured["closed"] is True


async def test_has_enabled_signoz_mcp_reads_by_sandbox(monkeypatch) -> None:
    sandbox_id = uuid.uuid4()
    captured: dict[str, Any] = {}

    class FakeConn:
        async def fetchrow(self, query: str, arg: uuid.UUID) -> dict[str, int]:
            captured["query"] = query
            captured["arg"] = arg
            return {"?column?": 1}

        async def close(self) -> None:
            pass

    async def fake_connect(database_url: str) -> FakeConn:
        captured["database_url"] = database_url
        return FakeConn()

    monkeypatch.setattr(_signoz_context.asyncpg, "connect", fake_connect)

    assert await _signoz_context.has_enabled_signoz_mcp("postgresql://db", str(sandbox_id))
    assert "sandbox_id = $1" in captured["query"]
    assert "user_id" not in captured["query"]
    assert captured["arg"] == sandbox_id


def test_stream_task_events_keeps_connection_alive_on_empty_queue(monkeypatch) -> None:
    class FakeQueue:
        def __init__(self) -> None:
            self.calls = 0

        def get(self, timeout: int):
            self.calls += 1
            if self.calls == 1:
                raise _pipeline_event_stream.queue.Empty
            return None

        def put(self, item) -> None:
            pass

    def fake_run_coroutine_threadsafe(coro, loop):
        coro.close()
        return None

    monkeypatch.setattr(_pipeline_event_stream.queue, "Queue", FakeQueue)
    monkeypatch.setattr(
        _pipeline_event_stream.asyncio,
        "run_coroutine_threadsafe",
        fake_run_coroutine_threadsafe,
    )

    gen = _pipeline_event_stream.stream_task_events(
        loop=asyncio.new_event_loop(),
        database_url="postgresql://db",
        task_id=str(uuid.uuid4()),
        cursor=None,
    )

    assert next(gen) == ": heartbeat\n\n"
    try:
        next(gen)
    except StopIteration:
        pass
    else:
        raise AssertionError("stream_task_events deveria encerrar ao receber sentinel None")


def test_done_full_text_becomes_text_event_when_chunks_are_missing() -> None:
    msg = types.SimpleNamespace(
        done=types.SimpleNamespace(
            full_text="Resposta final", prompt_tokens=10, completion_tokens=3
        )
    )

    assert _grpc_event_handlers.final_text_fallback_event(msg, streamed_text=False) == (
        "text",
        {"content": "Resposta final"},
    )
    assert _grpc_event_handlers.final_text_fallback_event(msg, streamed_text=True) is None


def test_provider_api_error_text_chunk_becomes_error_event() -> None:
    msg = types.SimpleNamespace(
        text_chunk=types.SimpleNamespace(
            text=(
                'API Error: 429 {"error":{"message":"Provider returned error",'
                '"code":429,"metadata":{"raw":"deepseek/deepseek-v4-flash:free '
                'is temporarily rate-limited upstream","provider_name":"Crucible",'
                '"is_byok":false}},"user_id":"user_should_not_leak"}'
            )
        )
    )

    event_type, data = _grpc_event_handlers.text_chunk_event(msg)

    assert event_type == "error"
    assert "429" in data["message"]
    assert "deepseek/deepseek-v4-flash:free" in data["message"]
    assert "Crucible" in data["message"]
    assert "user_should_not_leak" not in data["message"]


def test_clean_assistant_text_removes_tool_chatter_before_final_answer() -> None:
    raw = (
        'Search repository for "1556".Open regra_nf.py.Read relevant lines.'
        "**Diagnóstico**\nO problema está na regra de CFOP."
    )

    assert _assistant_output.clean_assistant_text(raw).startswith("**Diagnóstico**")


def test_clean_assistant_text_rejects_tool_plan_without_answer() -> None:
    raw = (
        'Search repo for "ticketlog".Open venda.py.Read the relevant segment.'
        "#### Bash tool call\n```bash\nrg ticketlog\n```"
    )

    assert _assistant_output.clean_assistant_text(raw) == ""


def test_clean_assistant_text_rejects_internal_english_draft() -> None:
    raw = (
        "Likely need to adjust motivo_movto to have recolha_notas flag. "
        "Then use view to select older sales. Search send methods.Open view."
    )

    assert _assistant_output.clean_assistant_text(raw) == ""


async def test_final_message_lookup_uses_latest_user_turn_as_floor() -> None:
    conversation_id = uuid.uuid4()
    task_created = datetime(2026, 5, 20, 17, 35, 15, tzinfo=UTC)
    user_created = task_created - timedelta(seconds=1)
    message_id = uuid.uuid4()
    content = "Resposta final limpa"

    class FakeConn:
        def __init__(self) -> None:
            self.fetch_args: tuple[Any, ...] | None = None

        async def fetchrow(self, query: str, *args: Any) -> dict[str, Any]:
            return {"created_at": user_created}

        async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
            self.fetch_args = args
            return [{"id": message_id, "content": content}]

    conn = FakeConn()

    existing = await _task_final_message._find_existing_response_message(
        conn,
        conversation_id,
        content,
        {"created_at": task_created},
    )

    assert existing and existing["id"] == message_id
    assert conn.fetch_args == (conversation_id, user_created)


async def test_clean_existing_final_message_refreshes_usage_metadata() -> None:
    message_id = uuid.uuid4()
    task = {
        "model_used": "openai/gpt-oss-120b:free",
        "prompt_tokens": 100,
        "completion_tokens": 25,
        "cost_usd": Decimal("0"),
    }

    class FakeConn:
        def __init__(self) -> None:
            self.execute_args: tuple[Any, ...] | None = None

        async def execute(self, query: str, *args: Any) -> None:
            self.execute_args = args

    conn = FakeConn()

    await _task_final_message._clean_existing_message(
        conn,
        {"id": message_id, "content": "Resposta final limpa"},
        "Resposta final limpa",
        task,
    )

    assert conn.execute_args == (
        "openai/gpt-oss-120b:free",
        100,
        25,
        Decimal("0"),
        message_id,
    )
