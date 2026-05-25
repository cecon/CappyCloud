from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from app.application.use_cases import mcp_telemetry as mcp_telemetry_module
from app.application.use_cases.mcp_telemetry import (
    GetMcpTelemetrySummary,
    McpTelemetryWindowError,
    call_tool_with_telemetry,
    caller_session_id,
    prune_mcp_invocations,
    resolve_trace_id,
    sanitize_arguments,
)
from app.domain.entities import UserMcpServer
from app.ports.mcp_telemetry import (
    McpTelemetryFilters,
    McpTelemetryRepository,
    McpToolInvocationRecord,
)


class _SummaryRepo(McpTelemetryRepository):
    def __init__(self) -> None:
        self.filters: McpTelemetryFilters | None = None
        self.cutoff: datetime | None = None

    async def record_invocation(self, record: McpToolInvocationRecord) -> None:
        _ = record

    async def summarize(
        self,
        filters: McpTelemetryFilters,
        *,
        registered_tool_names: set[str],
    ) -> dict[str, Any]:
        self.filters = filters
        return {"tools_never_used": sorted(registered_tool_names)}

    async def prune_before(self, cutoff: datetime) -> int:
        self.cutoff = cutoff
        return 3


def _server() -> UserMcpServer:
    return UserMcpServer(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        repository_id=uuid.uuid4(),
        name="Claude",
        token_hash="hash",
        token_preview="preview",
    )


def test_sanitize_redacts_keys_recursively_without_mutating_input() -> None:
    raw = {
        "query": "empresa",
        "apiKey": "abc",
        "nested": {"Authorization": "Bearer token", "normal": "ok"},
    }

    sanitized = sanitize_arguments(raw)

    assert sanitized["apiKey"] == "<redacted>"
    assert sanitized["nested"]["Authorization"] == "<redacted>"
    assert sanitized["nested"]["normal"] == "ok"
    assert raw["apiKey"] == "abc"


def test_sanitize_truncates_strings_lists_depth_and_coerces_values() -> None:
    class Custom:
        def __str__(self) -> str:
            return "custom-value"

    sanitized = sanitize_arguments(
        {
            "long": "x" * 2000,
            "items": list(range(55)),
            "deep": {"a": {"b": {"c": {"d": {"e": "too-deep"}}}}},
            "primitive": True,
            "custom": Custom(),
        }
    )

    assert sanitized["long"].startswith("x" * 500)
    assert sanitized["long"].endswith("(truncated:2000 chars total)")
    assert len(sanitized["items"]) == 51
    assert sanitized["items"][-1] == "<truncated:list-length>"
    assert sanitized["deep"]["a"]["b"]["c"]["d"] == "<truncated:depth>"
    assert sanitized["primitive"] is True
    assert sanitized["custom"] == "custom-value"
    assert mcp_telemetry_module._sanitize_dict({"x": "y"}, depth=5) == {"_": "<truncated:depth>"}


def test_trace_id_prefers_uuid_headers_and_session_is_truncated() -> None:
    request_id = uuid.uuid4()
    correlation_id = uuid.uuid4()

    assert resolve_trace_id({"x-request-id": str(request_id)}) == request_id
    assert (
        resolve_trace_id({"x-request-id": "not-a-uuid", "x-correlation-id": str(correlation_id)})
        == correlation_id
    )
    assert isinstance(resolve_trace_id({}), uuid.UUID)
    assert caller_session_id({"mcp-session-id": "s" * 250}) == "s" * 200


async def test_call_tool_with_telemetry_records_success() -> None:
    rows: list[McpToolInvocationRecord] = []
    trace_id = uuid.uuid4()

    result = await call_tool_with_telemetry(
        server=_server(),
        tool_name="repository_graph",
        arguments={"materialized": True, "token": "secret"},
        trace_id=trace_id,
        caller_user_agent="Claude",
        caller_session_id="session-1",
        metadata={"requested_tool_name": "smart_codebase_graph"},
        recorder=rows.append,
        call=lambda: _async_result({"ok": True}),
    )

    assert result == {"ok": True}
    assert len(rows) == 1
    row = rows[0]
    assert row.trace_id == trace_id
    assert row.status == "ok"
    assert row.materialized is True
    assert row.arguments_sanitized["token"] == "<redacted>"
    assert row.response_bytes is not None and row.response_bytes > 0
    assert row.response_hash is not None and len(row.response_hash) == 64
    assert row.metadata["requested_tool_name"] == "smart_codebase_graph"


async def test_call_tool_with_telemetry_accepts_string_materialized_flag() -> None:
    rows: list[McpToolInvocationRecord] = []

    await call_tool_with_telemetry(
        server=_server(),
        tool_name="repository_graph",
        arguments={"materialized": "yes"},
        trace_id=uuid.uuid4(),
        caller_user_agent=None,
        caller_session_id=None,
        metadata={},
        recorder=rows.append,
        call=lambda: _async_result({"ok": True}),
    )

    assert rows[0].materialized is True


async def test_call_tool_with_telemetry_records_and_reraises_errors() -> None:
    rows: list[McpToolInvocationRecord] = []

    async def fail() -> dict[str, Any]:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await call_tool_with_telemetry(
            server=_server(),
            tool_name="repository_search",
            arguments={"query": "x"},
            trace_id=uuid.uuid4(),
            caller_user_agent=None,
            caller_session_id=None,
            metadata={},
            recorder=rows.append,
            call=fail,
        )

    assert rows[0].status == "error"
    assert rows[0].error_summary == "boom"
    assert rows[0].response_hash is None


async def test_recorder_failure_does_not_block_success(caplog: pytest.LogCaptureFixture) -> None:
    def broken_recorder(record: McpToolInvocationRecord) -> None:
        _ = record
        raise RuntimeError("db offline")

    result = await call_tool_with_telemetry(
        server=_server(),
        tool_name="skills_search",
        arguments={},
        trace_id=uuid.uuid4(),
        caller_user_agent=None,
        caller_session_id=None,
        metadata={},
        recorder=broken_recorder,
        call=lambda: _async_result({"ok": True}),
    )

    assert result == {"ok": True}
    assert "mcp_telemetry_recorder_failed" in caplog.text


async def test_summary_rejects_invalid_or_too_large_windows() -> None:
    use_case = GetMcpTelemetrySummary(_SummaryRepo())
    now = datetime.now(UTC)

    with pytest.raises(McpTelemetryWindowError):
        await use_case.execute(
            from_ts=now,
            to_ts=now,
            repo_id=None,
            tool_name=None,
            registered_tool_names=set(),
        )
    with pytest.raises(McpTelemetryWindowError):
        await use_case.execute(
            from_ts=now,
            to_ts=now + timedelta(days=91),
            repo_id=None,
            tool_name=None,
            registered_tool_names=set(),
        )


async def test_summary_accepts_naive_datetimes_as_utc() -> None:
    repo = _SummaryRepo()
    now = datetime.now().replace(tzinfo=None)

    await GetMcpTelemetrySummary(repo).execute(
        from_ts=now,
        to_ts=now + timedelta(hours=1),
        repo_id=None,
        tool_name=None,
        registered_tool_names={"repository_search"},
    )

    assert repo.filters is not None
    assert repo.filters.from_ts.tzinfo is UTC


async def test_prune_uses_retention_days() -> None:
    repo = _SummaryRepo()

    deleted = await prune_mcp_invocations(repo, retention_days=10)

    assert deleted == 3
    assert repo.cutoff is not None
    assert repo.cutoff < datetime.now(UTC) - timedelta(days=9)


async def _async_result(value: dict[str, Any]) -> dict[str, Any]:
    return value
