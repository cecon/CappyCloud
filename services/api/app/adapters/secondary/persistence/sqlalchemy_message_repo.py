"""SQLAlchemy implementation of MessageRepository port."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Message as MsgEntity
from app.infrastructure.orm_models import Message as MsgORM
from app.ports.repositories import MessageRepository


class SQLAlchemyMessageRepository(MessageRepository):
    """Concrete MessageRepository backed by PostgreSQL via SQLAlchemy async."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_conversation(
        self, conversation_id: uuid.UUID
    ) -> list[MsgEntity]:
        result = await self._session.execute(
            select(MsgORM)
            .where(MsgORM.conversation_id == conversation_id)
            .order_by(MsgORM.created_at.asc())
        )
        return [self._to_entity(row) for row in result.scalars().all()]

    async def save(self, message: MsgEntity) -> MsgEntity:
        orm = MsgORM(
            id=message.id,
            conversation_id=message.conversation_id,
            role=message.role,
            content=message.content,
        )
        self._session.add(orm)
        await self._session.commit()
        await self._session.refresh(orm)
        return self._to_entity(orm)

    @staticmethod
    def _to_entity(row: MsgORM) -> MsgEntity:
        return MsgEntity(
            id=row.id,
            conversation_id=row.conversation_id,
            role=row.role,
            content=row.content,
            created_at=row.created_at,
        )
