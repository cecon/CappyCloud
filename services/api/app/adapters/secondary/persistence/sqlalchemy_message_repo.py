"""SQLAlchemy implementation of MessageRepository port."""

from __future__ import annotations

import uuid

from sqlalchemy import null, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Message as MsgEntity
from app.infrastructure.orm_models import Message as MsgORM
from app.infrastructure.orm_models_platform import AiModel
from app.ports.repositories import MessageRepository


class SQLAlchemyMessageRepository(MessageRepository):
    """Concrete MessageRepository backed by PostgreSQL via SQLAlchemy async."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_conversation(self, conversation_id: uuid.UUID) -> list[MsgEntity]:
        result = await self._session.execute(
            select(MsgORM)
            .where(MsgORM.conversation_id == conversation_id)
            .order_by(MsgORM.created_at.asc())
        )
        return [self._to_entity(row) for row in result.scalars().all()]

    async def save(self, message: MsgEntity) -> MsgEntity:
        values = {
            "id": message.id,
            "conversation_id": message.conversation_id,
            "role": message.role,
            "content": message.content,
            "model_used": message.model_used,
            "prompt_tokens": message.prompt_tokens,
            "completion_tokens": message.completion_tokens,
            "cost_usd": message.cost_usd,
        }
        values["payload_diagnostics"] = (
            message.payload_diagnostics if message.payload_diagnostics is not None else null()
        )
        orm = MsgORM(**values)
        self._session.add(orm)
        await self._session.commit()
        await self._session.refresh(orm)
        return self._to_entity(orm)

    async def get_model_pricing(self, model_used: str) -> tuple[float, float] | None:
        if not model_used:
            return None
        row = (
            await self._session.execute(
                select(
                    AiModel.input_cost_per_1m_usd,
                    AiModel.output_cost_per_1m_usd,
                )
                .where(AiModel.model_id == model_used)
                .where(AiModel.active.is_(True))
                .limit(1)
            )
        ).first()
        if row is None:
            return None
        input_cost = float(row[0] or 0)
        output_cost = float(row[1] or 0)
        return (input_cost, output_cost)

    @staticmethod
    def _to_entity(row: MsgORM) -> MsgEntity:
        return MsgEntity(
            id=row.id,
            conversation_id=row.conversation_id,
            role=row.role,
            content=row.content,
            created_at=row.created_at,
            model_used=row.model_used,
            prompt_tokens=row.prompt_tokens or 0,
            completion_tokens=row.completion_tokens or 0,
            cost_usd=float(row.cost_usd or 0),
            payload_diagnostics=row.payload_diagnostics,
        )
