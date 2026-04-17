"""AI Providers & Models HTTP router — catálogo de modelos e chaves de API."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import get_authenticated_user, get_db_session
from app.domain.entities import User
from app.infrastructure.encryption import get_encryptor
from app.infrastructure.orm_models import AiModel, AiProvider
from app.schemas import AiModelCreate, AiModelOut, AiProviderCreate, AiProviderOut

router = APIRouter(tags=["ai"])


# ── AI Providers ──────────────────────────────────────────────

@router.get("/ai-providers", response_model=list[AiProviderOut])
async def list_ai_providers(
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[AiProviderOut]:
    rows = await session.execute(select(AiProvider).order_by(AiProvider.name))
    return [AiProviderOut.model_validate(r) for r in rows.scalars()]


@router.post("/ai-providers", response_model=AiProviderOut, status_code=201)
async def create_ai_provider(
    body: AiProviderCreate,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AiProviderOut:
    enc = get_encryptor()
    provider = AiProvider(
        id=uuid.uuid4(),
        name=body.name,
        base_url=body.base_url,
        api_key_encrypted=enc.encrypt(body.api_key) if body.api_key else "",
    )
    session.add(provider)
    await session.commit()
    await session.refresh(provider)
    return AiProviderOut.model_validate(provider)


@router.patch("/ai-providers/{provider_id}/key", response_model=AiProviderOut)
async def update_ai_provider_key(
    provider_id: uuid.UUID,
    api_key: str,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AiProviderOut:
    provider = await session.get(AiProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider não encontrado")
    provider.api_key_encrypted = get_encryptor().encrypt(api_key)
    await session.commit()
    await session.refresh(provider)
    return AiProviderOut.model_validate(provider)


# ── AI Models ─────────────────────────────────────────────────

@router.get("/ai-models", response_model=list[AiModelOut])
async def list_ai_models(
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[AiModelOut]:
    rows = await session.execute(
        select(AiModel).where(AiModel.active == True).order_by(AiModel.display_name)  # noqa: E712
    )
    return [AiModelOut.model_validate(r) for r in rows.scalars()]


@router.post("/ai-models", response_model=AiModelOut, status_code=201)
async def create_ai_model(
    body: AiModelCreate,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AiModelOut:
    model = AiModel(
        id=uuid.uuid4(),
        provider_id=body.provider_id,
        model_id=body.model_id,
        display_name=body.display_name,
        capabilities=body.capabilities,
        is_default=body.is_default,
        context_window=body.context_window,
    )
    session.add(model)
    await session.commit()
    await session.refresh(model)
    return AiModelOut.model_validate(model)


@router.delete("/ai-models/{model_id}", status_code=204)
async def delete_ai_model(
    model_id: uuid.UUID,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    model = await session.get(AiModel, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Modelo não encontrado")
    await session.delete(model)
    await session.commit()
