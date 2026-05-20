"""Regression tests for CappyCloud agent runtime edge cases."""

from __future__ import annotations

import asyncio
import sys
import types
import uuid
from importlib import util
from pathlib import Path
from typing import Any


def _find_repo_root() -> Path:
    current = Path(__file__).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "services" / "cappycloud_agent").is_dir():
            return candidate
    raise RuntimeError("Não encontrei services/cappycloud_agent no worktree.")


ROOT = _find_repo_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_agent_pkg = types.ModuleType("services.cappycloud_agent")
_agent_pkg.__path__ = [str(ROOT / "services/cappycloud_agent")]  # type: ignore[attr-defined]
sys.modules.setdefault("services.cappycloud_agent", _agent_pkg)


def _load_module(name: str, path: Path) -> types.ModuleType:
    spec = util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_agent_context = _load_module(
    "services.cappycloud_agent._agent_context",
    ROOT / "services/cappycloud_agent/_agent_context.py",
)
_pipeline_helpers = _load_module(
    "services.cappycloud_agent._pipeline_helpers",
    ROOT / "services/cappycloud_agent/_pipeline_helpers.py",
)
_pipeline_event_stream = _load_module(
    "services.cappycloud_agent._pipeline_event_stream",
    ROOT / "services/cappycloud_agent/_pipeline_event_stream.py",
)
_grpc_event_handlers = _load_module(
    "services.cappycloud_agent._grpc_event_handlers",
    ROOT / "services/cappycloud_agent/_grpc_event_handlers.py",
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

    monkeypatch.setattr(_pipeline_helpers.asyncpg, "connect", fake_connect)

    assert await _pipeline_helpers.has_enabled_signoz_mcp("postgresql://db", str(sandbox_id))
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
