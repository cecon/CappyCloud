"""SQLAlchemy implementation of ConversationRepository port."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Conversation as ConvEntity
from app.infrastructure.orm_models import Conversation as ConvORM
from app.ports.repositories import ConversationRepository


class SQLAlchemyConversationRepository(ConversationRepository):
    """Concrete ConversationRepository backed by PostgreSQL via SQLAlchemy async."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_user(self, user_id: uuid.UUID) -> list[ConvEntity]:
        result = await self._session.execute(
            select(ConvORM)
            .where(ConvORM.user_id == user_id)
            .order_by(ConvORM.updated_at.desc())
        )
        return [self._to_entity(row) for row in result.scalars().all()]

    async def get(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> ConvEntity | None:
        result = await self._session.execute(
            select(ConvORM).where(
                ConvORM.id == conversation_id,
                ConvORM.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def save(self, conversation: ConvEntity) -> ConvEntity:
        orm = ConvORM(
            id=conversation.id,
            user_id=conversation.user_id,
            title=conversation.title,
        )
        self._session.add(orm)
        await self._session.commit()
        await self._session.refresh(orm)
        return self._to_entity(orm)

    async def update(self, conversation: ConvEntity) -> ConvEntity:
        result = await self._session.execute(
            select(ConvORM).where(ConvORM.id == conversation.id)
        )
        orm = result.scalar_one()
        orm.title = conversation.title
        await self._session.commit()
        await self._session.refresh(orm)
        return self._to_entity(orm)

    @staticmethod
    def _to_entity(row: ConvORM) -> ConvEntity:
        return ConvEntity(
            id=row.id,
            user_id=row.user_id,
            title=row.title,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
