"""SQLAlchemy policy for LLM model availability and user access."""

from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import UserRole
from app.infrastructure.orm_models_access import UserAiModelAccess
from app.infrastructure.orm_models_platform import AiModel, AiProvider
from app.ports.user_access import AiModelAccessPolicy


class SQLAlchemyAiModelAccessPolicy(AiModelAccessPolicy):
    """Aplica o gate global ``ai_models.active`` antes do acesso por utilizador."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve_model_for_user(
        self,
        user_id: uuid.UUID,
        role: UserRole,
        requested_model_id: str | None,
    ) -> str:
        model = await self._find_active_text_model(requested_model_id)
        if model is None:
            raise PermissionError("Modelo LLM indisponível ou desativado globalmente.")

        if role is UserRole.ADMIN:
            return model.model_id

        allowed = await self._session.execute(
            select(UserAiModelAccess.id).where(
                UserAiModelAccess.user_id == user_id,
                UserAiModelAccess.ai_model_id == model.id,
            )
        )
        if allowed.scalar_one_or_none() is None:
            raise PermissionError("Sem acesso ao modelo LLM solicitado.")
        return model.model_id

    async def resolve_model_uuid_for_user(
        self,
        user_id: uuid.UUID,
        role: UserRole,
        requested_model_id: str | None,
    ) -> uuid.UUID:
        model = await self._find_active_text_model(requested_model_id)
        if model is None:
            raise PermissionError("Modelo LLM indisponível ou desativado globalmente.")

        if role is UserRole.ADMIN:
            return model.id

        allowed = await self._session.execute(
            select(UserAiModelAccess.id).where(
                UserAiModelAccess.user_id == user_id,
                UserAiModelAccess.ai_model_id == model.id,
            )
        )
        if allowed.scalar_one_or_none() is None:
            raise PermissionError("Sem acesso ao modelo LLM solicitado.")
        return model.id

    async def _find_active_text_model(self, requested_model_id: str | None) -> AiModel | None:
        stmt = (
            select(AiModel)
            .join(AiProvider)
            .where(AiModel.active.is_(True))
            .where(AiProvider.active.is_(True))
            .where(text("ai_models.capabilities ? 'text'"))
        )
        if requested_model_id:
            stmt = stmt.where(AiModel.model_id == requested_model_id)

        rows = (await self._session.execute(stmt.order_by(AiModel.display_name))).scalars().all()
        if not rows:
            return None
        default = next((m for m in rows if bool((m.is_default or {}).get("text"))), None)
        return default or rows[0]
