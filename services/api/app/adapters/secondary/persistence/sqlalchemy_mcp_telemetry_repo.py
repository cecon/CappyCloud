"""SQLAlchemy persistence for MCP telemetry."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import case, delete, desc, distinct, func, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.orm_models_mcp import McpToolInvocation
from app.infrastructure.orm_models_platform import Repository
from app.ports.mcp_telemetry import (
    McpTelemetryFilters,
    McpTelemetryRepository,
    McpToolInvocationRecord,
)


class SQLAlchemyMcpTelemetryRepository(McpTelemetryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_invocation(self, record: McpToolInvocationRecord) -> None:
        self._session.add(
            McpToolInvocation(
                trace_id=record.trace_id,
                server_id=record.server_id,
                user_id=record.user_id,
                repo_id=record.repo_id,
                tool_name=record.tool_name,
                arguments_sanitized=record.arguments_sanitized,
                status=record.status,
                error_summary=record.error_summary,
                duration_ms=record.duration_ms,
                response_bytes=record.response_bytes,
                response_hash=record.response_hash,
                caller_user_agent=record.caller_user_agent,
                caller_session_id=record.caller_session_id,
                meta=record.metadata,
            )
        )
        await self._session.commit()

    async def summarize(
        self,
        filters: McpTelemetryFilters,
        *,
        registered_tool_names: set[str],
    ) -> dict[str, Any]:
        conditions = _conditions(filters)
        totals = await self._totals(conditions)
        by_tool = await self._by_tool(conditions)
        by_repo = await self._by_repo(conditions)
        top_errors = await self._top_errors(conditions)
        used_tools = {row["tool_name"] for row in by_tool}
        return {
            "window": {"from": filters.from_ts.isoformat(), "to": filters.to_ts.isoformat()},
            "filters": {
                "repo_id": str(filters.repo_id) if filters.repo_id else None,
                "tool_name": filters.tool_name,
            },
            "totals": totals,
            "by_tool": by_tool,
            "by_repo": by_repo,
            "tools_never_used": sorted(registered_tool_names - used_tools),
            "top_errors": top_errors,
        }

    async def prune_before(self, cutoff: datetime) -> int:
        result: CursorResult = await self._session.execute(  # type: ignore[assignment]
            delete(McpToolInvocation).where(McpToolInvocation.created_at < cutoff)
        )
        await self._session.commit()
        return int(result.rowcount or 0)

    async def _totals(self, conditions: list[Any]) -> dict[str, Any]:
        row = (
            await self._session.execute(
                select(
                    func.count(McpToolInvocation.id),
                    func.count(distinct(McpToolInvocation.trace_id)),
                    func.count(distinct(McpToolInvocation.user_id)),
                    func.count(distinct(McpToolInvocation.repo_id)),
                    func.sum(case((McpToolInvocation.status == "error", 1), else_=0)),
                    func.sum(case((McpToolInvocation.status == "timeout", 1), else_=0)),
                ).where(*conditions)
            )
        ).one()
        invocations = int(row[0] or 0)
        error_count = int(row[4] or 0)
        timeout_count = int(row[5] or 0)
        return {
            "invocations": invocations,
            "unique_traces": int(row[1] or 0),
            "unique_users": int(row[2] or 0),
            "unique_repos": int(row[3] or 0),
            "error_count": error_count,
            "timeout_count": timeout_count,
            "error_rate": ((error_count + timeout_count) / invocations) if invocations else 0.0,
        }

    async def _by_tool(self, conditions: list[Any]) -> list[dict[str, Any]]:
        rows = await self._session.execute(
            select(
                McpToolInvocation.tool_name,
                func.count(McpToolInvocation.id),
                func.sum(case((McpToolInvocation.status != "ok", 1), else_=0)),
                func.percentile_cont(0.5).within_group(McpToolInvocation.duration_ms),
                func.percentile_cont(0.95).within_group(McpToolInvocation.duration_ms),
                func.avg(McpToolInvocation.response_bytes),
            )
            .where(*conditions)
            .group_by(McpToolInvocation.tool_name)
            .order_by(desc(func.count(McpToolInvocation.id)))
        )
        return [
            {
                "tool_name": tool_name,
                "invocations": int(count or 0),
                "error_count": int(errors or 0),
                "p50_ms": int(p50 or 0),
                "p95_ms": int(p95 or 0),
                "avg_response_bytes": int(avg_bytes or 0),
            }
            for tool_name, count, errors, p50, p95, avg_bytes in rows.all()
        ]

    async def _by_repo(self, conditions: list[Any]) -> list[dict[str, Any]]:
        rows = await self._session.execute(
            select(
                McpToolInvocation.repo_id,
                Repository.slug,
                McpToolInvocation.tool_name,
                func.count(McpToolInvocation.id),
            )
            .join(Repository, Repository.id == McpToolInvocation.repo_id, isouter=True)
            .where(*conditions)
            .group_by(McpToolInvocation.repo_id, Repository.slug, McpToolInvocation.tool_name)
        )
        grouped: dict[str, dict[str, Any]] = {}
        tool_counts: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for repo_id, repo_slug, tool_name, count in rows.all():
            key = str(repo_id) if repo_id else ""
            grouped.setdefault(
                key,
                {
                    "repo_id": str(repo_id) if repo_id else None,
                    "repo_slug": repo_slug,
                    "invocations": 0,
                },
            )
            grouped[key]["invocations"] += int(count or 0)
            tool_counts[key].append({"tool_name": tool_name, "count": int(count or 0)})
        out = []
        for key, row in grouped.items():
            row["top_tools"] = sorted(
                tool_counts[key], key=lambda item: item["count"], reverse=True
            )[:5]
            out.append(row)
        return sorted(out, key=lambda item: item["invocations"], reverse=True)

    async def _top_errors(self, conditions: list[Any]) -> list[dict[str, Any]]:
        rows = await self._session.execute(
            select(
                McpToolInvocation.tool_name,
                McpToolInvocation.error_summary,
                func.count(McpToolInvocation.id),
            )
            .where(
                *conditions,
                McpToolInvocation.status != "ok",
                McpToolInvocation.error_summary.is_not(None),
            )
            .group_by(McpToolInvocation.tool_name, McpToolInvocation.error_summary)
            .order_by(desc(func.count(McpToolInvocation.id)))
            .limit(10)
        )
        return [
            {"tool_name": tool, "error_summary": error, "count": int(count or 0)}
            for tool, error, count in rows.all()
        ]


def _conditions(filters: McpTelemetryFilters) -> list[Any]:
    conditions: list[Any] = [
        McpToolInvocation.created_at >= filters.from_ts,
        McpToolInvocation.created_at <= filters.to_ts,
    ]
    if filters.repo_id is not None:
        conditions.append(McpToolInvocation.repo_id == filters.repo_id)
    if filters.tool_name:
        conditions.append(McpToolInvocation.tool_name == filters.tool_name)
    return conditions
