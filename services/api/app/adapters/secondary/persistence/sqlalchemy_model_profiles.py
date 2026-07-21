"""SQLAlchemy adapter for authorized model profile lookup."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import UserRole
from app.infrastructure.orm_models_access import UserAiModelAccess
from app.infrastructure.orm_models_platform import AiModel, AiProvider
from app.ports.model_profiles import AuthorizedModelProfile, ModelProfileLookupPort


class SQLAlchemyModelProfileLookup(ModelProfileLookupPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(
        self, user_id: uuid.UUID, role: UserRole
    ) -> list[AuthorizedModelProfile]:
        stmt = select(AiModel, AiProvider).join(AiProvider).order_by(AiProvider.name, AiModel.model_id)
        rows = (await self._session.execute(stmt)).all()
        allowed_ids: set[uuid.UUID] | None = None
        if role is not UserRole.ADMIN:
            allowed_ids = set(
                (
                    await self._session.execute(
                        select(UserAiModelAccess.ai_model_id).where(
                            UserAiModelAccess.user_id == user_id
                        )
                    )
                ).scalars()
            )

        profiles: list[AuthorizedModelProfile] = []
        for model, provider in rows:
            user_allowed = allowed_ids is None or model.id in allowed_ids
            active = bool(model.active and provider.active and user_allowed)
            reason = None
            if not provider.active:
                reason = "Provider inativo."
            elif not model.active:
                reason = "Modelo inativo."
            elif not user_allowed:
                reason = "Usuario sem acesso ao modelo."
            profiles.append(
                AuthorizedModelProfile(
                    model_id=model.model_id,
                    display_name=model.display_name,
                    provider=provider.name,
                    active=bool(model.active),
                    provider_active=bool(provider.active),
                    capabilities=list(model.capabilities or []),
                    context_window=int(model.context_window or 0),
                    input_cost_per_1m_usd=(
                        float(model.input_cost_per_1m_usd)
                        if model.input_cost_per_1m_usd is not None
                        else None
                    ),
                    output_cost_per_1m_usd=(
                        float(model.output_cost_per_1m_usd)
                        if model.output_cost_per_1m_usd is not None
                        else None
                    ),
                    unavailable_reason=None if active else reason,
                )
            )
        return profiles

