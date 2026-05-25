"""MCP telemetry helpers used by the HTTP runtime and admin reporting."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Any

from app.domain.entities import UserMcpServer
from app.ports.mcp_telemetry import (
    McpTelemetryFilters,
    McpTelemetryRepository,
    McpToolInvocationRecord,
)

log = logging.getLogger(__name__)

MAX_TELEMETRY_WINDOW_DAYS = 90
_MAX_STRING_LENGTH = 500
_MAX_LIST_LENGTH = 50
_MAX_DEPTH = 4
_SENSITIVE_KEYS = {
    "token",
    "password",
    "secret",
    "key",
    "bearer",
    "authorization",
    "apikey",
    "api_key",
    "auth",
    "credential",
    "credentials",
    "cookie",
}

TelemetryRecorder = Callable[[McpToolInvocationRecord], None]


class McpTelemetryWindowError(ValueError):
    """Raised when an admin asks for an invalid telemetry window."""


def sanitize_arguments(args: dict[str, Any] | None) -> dict[str, Any]:
    if not args:
        return {}
    return _sanitize_dict(args, depth=0)


def resolve_trace_id(headers: Mapping[str, str]) -> uuid.UUID:
    # TODO: Replace this MCP-local resolver with global request-id middleware.
    for header_name in ("x-request-id", "x-correlation-id"):
        raw = headers.get(header_name) or headers.get(header_name.title())
        if not raw:
            continue
        try:
            return uuid.UUID(raw.strip())
        except ValueError:
            log.debug("Ignoring non-UUID %s header for MCP telemetry.", header_name)
    return uuid.uuid4()


def caller_session_id(headers: Mapping[str, str]) -> str | None:
    raw = headers.get("mcp-session-id") or headers.get("Mcp-Session-Id")
    if raw is None:
        return None
    value = raw.strip()
    return value[:200] or None


async def call_tool_with_telemetry(
    *,
    server: UserMcpServer,
    tool_name: str,
    arguments: dict[str, Any],
    trace_id: uuid.UUID,
    caller_user_agent: str | None,
    caller_session_id: str | None,
    metadata: dict[str, Any],
    recorder: TelemetryRecorder,
    call: Callable[[], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    start = monotonic()
    status = "ok"
    error_summary: str | None = None
    response_bytes: int | None = None
    response_hash: str | None = None
    try:
        response = await call()
        encoded = _telemetry_json_bytes(response)
        response_bytes = len(encoded)
        response_hash = hashlib.sha256(encoded[:4096]).hexdigest()
        return response
    except Exception as exc:
        is_timeout = isinstance(exc, (TimeoutError, asyncio.TimeoutError)) or (
            "Timeout" in exc.__class__.__name__
        )
        status = "timeout" if is_timeout else "error"
        error_summary = str(exc)[:500]
        raise
    finally:
        duration_ms = int((monotonic() - start) * 1000)
        record = McpToolInvocationRecord(
            trace_id=trace_id,
            server_id=server.id,
            user_id=server.user_id,
            repo_id=server.repository_id,
            tool_name=tool_name,
            arguments_sanitized=sanitize_arguments(arguments),
            status=status,
            error_summary=error_summary,
            duration_ms=duration_ms,
            response_bytes=response_bytes,
            response_hash=response_hash,
            materialized=_materialized_flag(tool_name, arguments),
            caller_user_agent=caller_user_agent,
            caller_session_id=caller_session_id,
            metadata=metadata,
        )
        try:
            recorder(record)
        except Exception:
            log.exception("mcp_telemetry_recorder_failed tool=%s", tool_name)


class GetMcpTelemetrySummary:
    def __init__(self, repo: McpTelemetryRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        *,
        from_ts: datetime,
        to_ts: datetime,
        repo_id: uuid.UUID | None,
        tool_name: str | None,
        registered_tool_names: set[str],
    ) -> dict[str, Any]:
        from_ts = _as_utc(from_ts)
        to_ts = _as_utc(to_ts)
        if to_ts <= from_ts:
            raise McpTelemetryWindowError("A janela de telemetria deve ter início antes do fim.")
        if to_ts - from_ts > timedelta(days=MAX_TELEMETRY_WINDOW_DAYS):
            raise McpTelemetryWindowError("A janela máxima de telemetria é de 90 dias.")
        return await self._repo.summarize(
            McpTelemetryFilters(
                from_ts=from_ts,
                to_ts=to_ts,
                repo_id=repo_id,
                tool_name=tool_name,
            ),
            registered_tool_names=registered_tool_names,
        )


async def prune_mcp_invocations(repo: McpTelemetryRepository, *, retention_days: int) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=max(1, retention_days))
    return await repo.prune_before(cutoff)


def _sanitize_dict(args: dict[str, Any], *, depth: int) -> dict[str, Any]:
    if depth > _MAX_DEPTH:
        return {"_": "<truncated:depth>"}
    out: dict[str, Any] = {}
    for key, value in args.items():
        key_s = str(key)
        if key_s.lower() in _SENSITIVE_KEYS:
            out[key_s] = "<redacted>"
        else:
            out[key_s] = _sanitize_value(value, depth=depth + 1)
    return out


def _sanitize_value(value: Any, *, depth: int) -> Any:
    if depth > _MAX_DEPTH:
        return "<truncated:depth>"
    if isinstance(value, dict):
        return _sanitize_dict(value, depth=depth)
    if isinstance(value, list):
        items = [_sanitize_value(item, depth=depth + 1) for item in value[:_MAX_LIST_LENGTH]]
        if len(value) > _MAX_LIST_LENGTH:
            items.append("<truncated:list-length>")
        return items
    if isinstance(value, str):
        return _truncate_string(value)
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return _truncate_string(str(value))


def _truncate_string(value: str) -> str:
    if len(value) <= _MAX_STRING_LENGTH:
        return value
    return f"{value[:_MAX_STRING_LENGTH]}...(truncated:{len(value)} chars total)"


def _telemetry_json_bytes(response: dict[str, Any]) -> bytes:
    return json.dumps(response, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")


def _materialized_flag(tool_name: str, arguments: dict[str, Any]) -> bool | None:
    if tool_name != "repository_graph":
        return None
    value = arguments.get("materialized")
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "sim"}


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
