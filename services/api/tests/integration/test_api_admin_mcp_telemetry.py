from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.adapters.primary.http.admin_mcp_telemetry import get_mcp_telemetry_repo
from app.main import app
from app.ports.mcp_telemetry import (
    McpTelemetryFilters,
    McpTelemetryRepository,
    McpToolInvocationRecord,
)
from httpx import AsyncClient


class _FakeTelemetryRepo(McpTelemetryRepository):
    def __init__(self) -> None:
        self.filters: McpTelemetryFilters | None = None

    async def record_invocation(self, record: McpToolInvocationRecord) -> None:
        _ = record

    async def summarize(
        self,
        filters: McpTelemetryFilters,
        *,
        registered_tool_names: set[str],
    ) -> dict[str, Any]:
        self.filters = filters
        return {
            "window": {"from": filters.from_ts.isoformat(), "to": filters.to_ts.isoformat()},
            "filters": {"repo_id": None, "tool_name": filters.tool_name},
            "totals": {
                "invocations": 2,
                "unique_traces": 2,
                "unique_users": 1,
                "unique_repos": 1,
                "error_count": 1,
                "timeout_count": 0,
                "error_rate": 0.5,
            },
            "by_tool": [
                {
                    "tool_name": "repository_search",
                    "invocations": 2,
                    "error_count": 1,
                    "p50_ms": 10,
                    "p95_ms": 20,
                    "avg_response_bytes": 100,
                }
            ],
            "by_repo": [],
            "tools_never_used": sorted(registered_tool_names - {"repository_search"}),
            "top_errors": [{"tool_name": "repository_search", "error_summary": "boom", "count": 1}],
        }

    async def prune_before(self, cutoff: datetime) -> int:
        _ = cutoff
        return 0


class TestAdminMcpTelemetry:
    async def test_summary_requires_admin(
        self,
        client: AsyncClient,
        user_headers: dict[str, str],
    ) -> None:
        now = datetime.now(UTC)
        response = await client.get(
            "/api/admin/mcp/telemetry",
            params={"from": now.isoformat(), "to": (now + timedelta(hours=1)).isoformat()},
            headers=user_headers,
        )

        assert response.status_code == 403

    async def test_summary_returns_aggregates_for_admin(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
    ) -> None:
        fake = _FakeTelemetryRepo()
        app.dependency_overrides[get_mcp_telemetry_repo] = lambda: fake
        now = datetime.now(UTC)

        response = await client.get(
            "/api/admin/mcp/telemetry",
            params={
                "from": now.isoformat(),
                "to": (now + timedelta(hours=1)).isoformat(),
                "tool_name": "repository_search",
            },
            headers=admin_headers,
        )

        assert response.status_code == 200
        body = response.json()
        assert body["totals"]["invocations"] == 2
        assert body["by_tool"][0]["tool_name"] == "repository_search"
        assert "repository_search" not in body["tools_never_used"]
        assert fake.filters is not None
        assert fake.filters.tool_name == "repository_search"

    async def test_summary_rejects_windows_over_90_days(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
    ) -> None:
        now = datetime.now(UTC)

        response = await client.get(
            "/api/admin/mcp/telemetry",
            params={"from": now.isoformat(), "to": (now + timedelta(days=91)).isoformat()},
            headers=admin_headers,
        )

        assert response.status_code == 400
