"""SQLAlchemy implementation of AiModelCapabilityLookup port."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.orm_models_platform import AiModel
from app.ports.repositories import AiModelCapabilityLookup


class SQLAlchemyAiModelCapabilityLookup(AiModelCapabilityLookup):
    """Concrete adapter usando ``ai_models.capabilities`` (JSONB array)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def is_vision_capable(self, model_id: str) -> bool:
        if not model_id or model_id in {"cappycloud", "default"}:
            return False
        row = (
            await self._session.execute(
                select(AiModel.capabilities)
                .where(AiModel.model_id == model_id)
                .where(AiModel.active.is_(True))
                .limit(1)
            )
        ).first()
        if row is None or row[0] is None:
            return False
        caps = row[0]
        if isinstance(caps, list):
            return "vision" in caps
        return False
