"""SQLAlchemy policy for LLM model availability and user access."""

from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import UserRole
from app.infrastructure.orm_models_access import UserAiModelAccess
from app.infrastructure.orm_models_platform import AiModel, AiProvider
from app.ports.user_access import AiModelAccessPolicy


def parse_model_row_id(requested: str | None) -> uuid.UUID | None:
    """Id da linha de ``ai_models`` quando o pedido vem do seletor do chat.

    O mesmo ``model_id`` pode existir em providers diferentes (ex.: o Opus no
    Azure e no proxy do Lynn). O chat manda o id da linha; scripts e conversas
    antigas mandam o ``model_id`` e continuam valendo.
    """
    if not requested:
        return None
    try:
        return uuid.UUID(requested)
    except ValueError:
        return None


def order_candidates(rows: list[AiModel], requested_model_id: str | None) -> list[AiModel]:
    """A default de texto primeiro; sem pedido, só ela (ou a primeira por nome)."""
    ordered = sorted(rows, key=lambda m: not bool((m.is_default or {}).get("text")))
    return ordered if requested_model_id else ordered[:1]


def choose_model(candidates: list[AiModel], role: UserRole, allowed_ids: set[uuid.UUID]) -> AiModel:
    """Admin leva a primeira candidata; os demais, a primeira liberada para eles."""
    if not candidates:
        raise PermissionError("Modelo LLM indisponível ou desativado globalmente.")
    if role is UserRole.ADMIN:
        return candidates[0]
    model = next((m for m in candidates if m.id in allowed_ids), None)
    if model is None:
        raise PermissionError("Sem acesso ao modelo LLM solicitado.")
    return model


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
        model = await self._resolve(user_id, role, requested_model_id)
        return model.model_id

    async def resolve_model_uuid_for_user(
        self,
        user_id: uuid.UUID,
        role: UserRole,
        requested_model_id: str | None,
    ) -> uuid.UUID:
        model = await self._resolve(user_id, role, requested_model_id)
        return model.id

    async def _resolve(
        self,
        user_id: uuid.UUID,
        role: UserRole,
        requested_model_id: str | None,
    ) -> AiModel:
        candidates = await self._active_text_models(requested_model_id)
        allowed: set[uuid.UUID] = set()
        if candidates and role is not UserRole.ADMIN:
            allowed = set(
                (
                    await self._session.execute(
                        select(UserAiModelAccess.ai_model_id).where(
                            UserAiModelAccess.user_id == user_id,
                            UserAiModelAccess.ai_model_id.in_([m.id for m in candidates]),
                        )
                    )
                )
                .scalars()
                .all()
            )
        return choose_model(candidates, role, allowed)

    async def _active_text_models(self, requested_model_id: str | None) -> list[AiModel]:
        """Linhas candidatas, a default de texto primeiro.

        Id da linha: só ela. ``model_id``: todas as linhas com esse nome. Vazio:
        o catálogo inteiro (a default, ou a primeira por nome).
        """
        stmt = (
            select(AiModel)
            .join(AiProvider)
            .where(AiModel.active.is_(True))
            .where(AiProvider.active.is_(True))
            .where(text("ai_models.capabilities ? 'text'"))
        )
        row_id = parse_model_row_id(requested_model_id)
        if row_id is not None:
            stmt = stmt.where(AiModel.id == row_id)
        elif requested_model_id:
            stmt = stmt.where(AiModel.model_id == requested_model_id)

        rows = (await self._session.execute(stmt.order_by(AiModel.display_name))).scalars().all()
        return order_candidates(list(rows), requested_model_id)
