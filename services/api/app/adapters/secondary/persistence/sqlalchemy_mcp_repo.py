"""SQLAlchemy implementation of McpServerRepository port (ADR-004 §6)."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import McpServer as McpServerEntity
from app.infrastructure.orm_models_mcp import McpServer as McpServerORM
from app.ports.mcp_repository import McpServerRepository


class SQLAlchemyMcpRepository(McpServerRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_sandbox(self, sandbox_id: uuid.UUID) -> list[McpServerEntity]:
        rows = await self._session.execute(
            select(McpServerORM)
            .where(McpServerORM.sandbox_id == sandbox_id)
            .order_by(McpServerORM.created_at)
        )
        return [self._to_entity(r) for r in rows.scalars()]

    async def get(self, mcp_id: uuid.UUID, sandbox_id: uuid.UUID) -> McpServerEntity | None:
        row = await self._session.get(McpServerORM, mcp_id)
        if not row or row.sandbox_id != sandbox_id:
            return None
        return self._to_entity(row)

    async def get_by_name(self, name: str, sandbox_id: uuid.UUID) -> McpServerEntity | None:
        row = await self._session.scalar(
            select(McpServerORM).where(
                McpServerORM.sandbox_id == sandbox_id,
                McpServerORM.name == name,
            )
        )
        return self._to_entity(row) if row else None

    async def create(self, mcp: McpServerEntity) -> McpServerEntity:
        orm = McpServerORM(
            id=mcp.id,
            sandbox_id=mcp.sandbox_id,
            name=mcp.name,
            command=mcp.command,
            args=list(mcp.args),
            env=dict(mcp.env),
            enabled=mcp.enabled,
        )
        self._session.add(orm)
        await self._session.commit()
        await self._session.refresh(orm)
        return self._to_entity(orm)

    async def update(self, mcp: McpServerEntity) -> McpServerEntity:
        orm = await self._session.get(McpServerORM, mcp.id)
        if not orm or orm.sandbox_id != mcp.sandbox_id:
            raise ValueError(f"McpServer {mcp.id} not found for sandbox {mcp.sandbox_id}")
        orm.name = mcp.name
        orm.command = mcp.command
        orm.args = list(mcp.args)
        orm.env = dict(mcp.env)
        orm.enabled = mcp.enabled
        await self._session.commit()
        await self._session.refresh(orm)
        return self._to_entity(orm)

    async def delete(self, mcp_id: uuid.UUID, sandbox_id: uuid.UUID) -> bool:
        result: CursorResult = await self._session.execute(  # type: ignore[assignment]
            delete(McpServerORM).where(
                McpServerORM.id == mcp_id,
                McpServerORM.sandbox_id == sandbox_id,
            )
        )
        await self._session.commit()
        return result.rowcount > 0

    @staticmethod
    def _to_entity(orm: McpServerORM) -> McpServerEntity:
        return McpServerEntity(
            id=orm.id,
            sandbox_id=orm.sandbox_id,
            name=orm.name,
            command=orm.command,
            args=list(orm.args or []),
            env=dict(orm.env or {}),
            enabled=orm.enabled,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )
