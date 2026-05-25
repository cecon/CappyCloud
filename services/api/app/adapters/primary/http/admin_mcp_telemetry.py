"""Admin HTTP endpoint for MCP telemetry aggregates."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import get_db_session, require_role
from app.adapters.secondary.persistence.sqlalchemy_mcp_telemetry_repo import (
    SQLAlchemyMcpTelemetryRepository,
)
from app.application.use_cases.mcp_telemetry import (
    GetMcpTelemetrySummary,
    McpTelemetryWindowError,
)
from app.application.use_cases.repository_mcp import CANONICAL_TOOLS
from app.domain.entities import User, UserRole
from app.ports.mcp_telemetry import McpTelemetryRepository

router = APIRouter(prefix="/admin/mcp", tags=["admin-mcp"])


def get_mcp_telemetry_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> McpTelemetryRepository:
    return SQLAlchemyMcpTelemetryRepository(session)


@router.get("/telemetry")
async def get_mcp_telemetry(
    current: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    repo: Annotated[McpTelemetryRepository, Depends(get_mcp_telemetry_repo)],
    from_ts: Annotated[datetime, Query(alias="from")],
    to_ts: Annotated[datetime, Query(alias="to")],
    repo_id: uuid.UUID | None = None,
    tool_name: str | None = None,
) -> dict[str, Any]:
    _ = current
    try:
        return await GetMcpTelemetrySummary(repo).execute(
            from_ts=from_ts,
            to_ts=to_ts,
            repo_id=repo_id,
            tool_name=tool_name,
            registered_tool_names={str(tool["name"]) for tool in CANONICAL_TOOLS},
        )
    except McpTelemetryWindowError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
