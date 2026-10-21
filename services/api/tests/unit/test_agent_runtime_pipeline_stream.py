"""Regression tests for agent pipeline helpers and task event streaming."""

from __future__ import annotations

import asyncio
import json
import types
import uuid
from typing import Any

from .agent_runtime_test_loader import (
    pipeline_event_stream as _pipeline_event_stream,
)
from .agent_runtime_test_loader import (
    pipeline_helpers as _pipeline_helpers,
)
from .agent_runtime_test_loader import (
    signoz_context as _signoz_context,
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


def test_stream_task_events_preserves_order_until_sentinel(monkeypatch) -> None:
    ordered_items = [
        ("status", {"message": "Preparando"}, 1),
        ("tool_start", {"name": "Bash", "input": "{}", "id": "toolu_1"}, 2),
        ("done", {"prompt_tokens": 1, "completion_tokens": 2}, 3),
        None,
    ]

    class FakeQueue:
        def get(self, timeout: int):
            del timeout
            return ordered_items.pop(0)

        def put(self, item) -> None:
            pass

    def fake_run_coroutine_threadsafe(coro, loop):
        del loop
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

    payloads = [json.loads(next(gen)[6:]) for _ in range(3)]

    assert [payload["type"] for payload in payloads] == ["status", "tool_start", "done"]
    assert [payload["cursor"] for payload in payloads] == [1, 2, 3]
