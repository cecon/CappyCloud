"""HTTP adapter administrativo para catálogo LLM (ADR-006).

Endpoints (todos ADMIN):

- GET    /admin/providers              → lista providers (com ``last_synced_at`` e nº modelos)
- POST   /admin/providers/{id}/sync    → dispara sync do provider (hoje só OpenRouter)
- GET    /admin/models?tier&provider   → lista modelos com filtros
- PATCH  /admin/models/{id}            → edita ``tier`` ou ``active``
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import require_role, require_super_admin
from app.adapters.primary.http.deps_base import get_db_session
from app.domain.entities import ModelTier, UserRole
from app.infrastructure.orm_models import AiModel, AiProvider
from app.schemas import AiModelOut, AiModelSyncResult

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)


class AdminProviderOut(BaseModel):
    id: uuid.UUID
    name: str
    base_url: str
    active: bool
    last_synced_at: str | None = None
    models_count: int = 0


@router.get("/providers", response_model=list[AdminProviderOut])
async def list_providers(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[AdminProviderOut]:
    """Lista providers com contagem de modelos e ``last_synced_at`` (ADR-006 §5)."""
    counts_q = select(AiModel.provider_id, func.count(AiModel.id)).group_by(AiModel.provider_id)
    rows = (await session.execute(counts_q)).all()
    counts: dict[uuid.UUID, int] = {row[0]: int(row[1]) for row in rows}
    providers = (
        (await session.execute(select(AiProvider).order_by(AiProvider.name))).scalars().all()
    )
    return [
        AdminProviderOut(
            id=p.id,
            name=p.name,
            base_url=p.base_url,
            active=p.active,
            last_synced_at=p.last_synced_at.isoformat() if p.last_synced_at else None,
            models_count=int(counts.get(p.id, 0)),
        )
        for p in providers
    ]


@router.post(
    "/providers/{provider_id}/sync",
    response_model=AiModelSyncResult,
    dependencies=[Depends(require_super_admin)],
)
async def sync_provider(
    provider_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AiModelSyncResult:
    """Dispara sync do provider. Hoje só ``OpenRouter`` é suportado nativamente
    (futuros adapters virão no PR de Azure AI Foundry — ADR-006 §1).
    """
    provider = await session.get(AiProvider, provider_id)
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Provider não encontrado."
        )
    if provider.name != "OpenRouter":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Sync para '{provider.name}' ainda não implementado.",
        )
    # Reutiliza o sync existente no router ``ai_models``:
    from app.adapters.primary.http.ai_models import sync_ai_models_from_openrouter

    return await sync_ai_models_from_openrouter(session)


class AdminModelFilter(BaseModel):
    provider_id: uuid.UUID | None = None
    tier: ModelTier | None = None
    only_active: bool = False


@router.get("/models", response_model=list[AiModelOut])
async def list_models_admin(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    provider_id: uuid.UUID | None = None,
    tier: ModelTier | None = None,
    only_active: bool = False,
) -> list[AiModelOut]:
    """Lista admin com filtros opcionais (sem filtro por user — ADMIN vê tudo)."""
    stmt = select(AiModel).order_by(AiModel.display_name)
    if provider_id is not None:
        stmt = stmt.where(AiModel.provider_id == provider_id)
    if tier is not None:
        stmt = stmt.where(AiModel.tier == tier.value)
    if only_active:
        stmt = stmt.where(AiModel.active.is_(True))
    rows = await session.execute(stmt)
    return [AiModelOut.model_validate(r) for r in rows.scalars()]


class AdminModelPatch(BaseModel):
    active: bool | None = None
    tier: ModelTier | None = None


@router.patch(
    "/models/{model_id}",
    response_model=AiModelOut,
    dependencies=[Depends(require_super_admin)],
)
async def patch_model_admin(
    model_id: uuid.UUID,
    body: AdminModelPatch,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AiModelOut:
    model = await session.get(AiModel, model_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Modelo não encontrado.")
    if body.active is not None:
        model.active = body.active
    if body.tier is not None:
        model.tier = body.tier.value
    await session.commit()
    await session.refresh(model)
    return AiModelOut.model_validate(model)
