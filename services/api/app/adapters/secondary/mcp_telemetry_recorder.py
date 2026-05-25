"""Fire-and-forget MCP telemetry recording using the app database."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from app.adapters.secondary.persistence.sqlalchemy_mcp_telemetry_repo import (
    SQLAlchemyMcpTelemetryRepository,
)
from app.infrastructure.database import async_session_factory
from app.ports.mcp_telemetry import McpToolInvocationRecord

log = logging.getLogger(__name__)


def schedule_mcp_tool_invocation(record: McpToolInvocationRecord) -> None:
    try:
        asyncio.get_running_loop().create_task(_record_mcp_tool_invocation(record))
    except RuntimeError:
        log.warning("mcp_telemetry_drop_no_running_loop tool=%s", record.tool_name)


async def _record_mcp_tool_invocation(record: McpToolInvocationRecord) -> None:
    try:
        async with async_session_factory() as session:
            await SQLAlchemyMcpTelemetryRepository(session).record_invocation(record)
    except Exception:
        log.exception(
            "mcp_telemetry_insert_failed tool=%s trace_id=%s", record.tool_name, record.trace_id
        )


async def prune_mcp_invocations(*, retention_days: int) -> int:
    try:
        async with async_session_factory() as session:
            cutoff = datetime.now(UTC) - timedelta(days=max(1, retention_days))
            deleted = await SQLAlchemyMcpTelemetryRepository(session).prune_before(cutoff)
            log.info("mcp_telemetry_pruned deleted=%s retention_days=%s", deleted, retention_days)
            return deleted
    except Exception:
        log.exception("mcp_telemetry_prune_failed")
        return 0
