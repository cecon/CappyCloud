"""SQLAlchemy adapter para ``ModelsByTierLookup`` (ADR-006 §3)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.admin_user_access import ModelsByTierLookup
from app.domain.entities import ModelTier
from app.infrastructure.orm_models_platform import AiModel as AiModelORM


class SQLAlchemyModelsByTierLookup(ModelsByTierLookup):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active_model_ids_by_tier(self, tier: ModelTier) -> list[uuid.UUID]:
        result = await self._session.execute(
            select(AiModelORM.id).where(AiModelORM.tier == tier.value, AiModelORM.active.is_(True))
        )
        return list(result.scalars().all())
