"""SQLAlchemy adapter for user-scoped HTTP MCP servers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import UserMcpServer as UserMcpServerEntity
from app.infrastructure.orm_models_mcp import UserMcpServer as UserMcpServerORM
from app.ports.mcp_repository import UserMcpServerRepository


class SQLAlchemyUserMcpServerRepository(UserMcpServerRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(self, user_id: uuid.UUID) -> list[UserMcpServerEntity]:
        rows = await self._session.execute(
            select(UserMcpServerORM)
            .where(UserMcpServerORM.user_id == user_id)
            .order_by(UserMcpServerORM.created_at)
        )
        return [self._to_entity(row) for row in rows.scalars()]

    async def get(self, server_id: uuid.UUID, user_id: uuid.UUID) -> UserMcpServerEntity | None:
        row = await self._session.get(UserMcpServerORM, server_id)
        if row is None or row.user_id != user_id:
            return None
        return self._to_entity(row)

    async def get_by_id(self, server_id: uuid.UUID) -> UserMcpServerEntity | None:
        row = await self._session.get(UserMcpServerORM, server_id)
        return self._to_entity(row) if row else None

    async def get_by_name(self, name: str, user_id: uuid.UUID) -> UserMcpServerEntity | None:
        row = await self._session.scalar(
            select(UserMcpServerORM).where(
                UserMcpServerORM.user_id == user_id,
                UserMcpServerORM.name == name,
            )
        )
        return self._to_entity(row) if row else None

    async def get_by_token_hash(self, token_hash: str) -> UserMcpServerEntity | None:
        row = await self._session.scalar(
            select(UserMcpServerORM).where(UserMcpServerORM.token_hash == token_hash)
        )
        return self._to_entity(row) if row else None

    async def create(self, server: UserMcpServerEntity) -> UserMcpServerEntity:
        row = UserMcpServerORM(
            id=server.id,
            user_id=server.user_id,
            repository_id=server.repository_id,
            name=server.name,
            token_hash=server.token_hash,
            token_preview=server.token_preview,
            enabled=server.enabled,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_entity(row)

    async def update(self, server: UserMcpServerEntity) -> UserMcpServerEntity:
        row = await self._session.get(UserMcpServerORM, server.id)
        if row is None or row.user_id != server.user_id:
            raise ValueError(f"UserMcpServer {server.id} not found")
        row.repository_id = server.repository_id
        row.name = server.name
        row.token_hash = server.token_hash
        row.token_preview = server.token_preview
        row.enabled = server.enabled
        row.last_used_at = server.last_used_at
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_entity(row)

    async def delete(self, server_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        result: CursorResult = await self._session.execute(  # type: ignore[assignment]
            delete(UserMcpServerORM).where(
                UserMcpServerORM.id == server_id,
                UserMcpServerORM.user_id == user_id,
            )
        )
        await self._session.commit()
        return result.rowcount > 0

    async def touch_last_used(self, server_id: uuid.UUID) -> None:
        row = await self._session.get(UserMcpServerORM, server_id)
        if row is None:
            return
        row.last_used_at = datetime.now(UTC)
        await self._session.commit()

    @staticmethod
    def _to_entity(row: UserMcpServerORM) -> UserMcpServerEntity:
        return UserMcpServerEntity(
            id=row.id,
            user_id=row.user_id,
            repository_id=row.repository_id,
            name=row.name,
            token_hash=row.token_hash,
            token_preview=row.token_preview,
            enabled=row.enabled,
            created_at=row.created_at,
            updated_at=row.updated_at,
            last_used_at=row.last_used_at,
        )
