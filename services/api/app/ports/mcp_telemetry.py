"""Ports and DTOs for MCP tool invocation telemetry."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class McpToolInvocationRecord:
    trace_id: uuid.UUID
    server_id: uuid.UUID | None
    user_id: uuid.UUID | None
    repo_id: uuid.UUID | None
    tool_name: str
    arguments_sanitized: dict[str, Any]
    status: str
    duration_ms: int
    error_summary: str | None = None
    response_bytes: int | None = None
    response_hash: str | None = None
    caller_user_agent: str | None = None
    caller_session_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class McpTelemetryFilters:
    from_ts: datetime
    to_ts: datetime
    repo_id: uuid.UUID | None = None
    tool_name: str | None = None


class McpTelemetryRepository(ABC):
    @abstractmethod
    async def record_invocation(self, record: McpToolInvocationRecord) -> None:
        """Persist one MCP tool invocation."""

    @abstractmethod
    async def summarize(
        self,
        filters: McpTelemetryFilters,
        *,
        registered_tool_names: set[str],
    ) -> dict[str, Any]:
        """Return aggregate telemetry for an admin window."""

    @abstractmethod
    async def prune_before(self, cutoff: datetime) -> int:
        """Delete old telemetry rows and return the deleted count."""
