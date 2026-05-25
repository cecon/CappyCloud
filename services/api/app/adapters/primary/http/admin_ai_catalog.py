"""HTTP adapter administrativo para catálogo LLM (ADR-006).

Endpoints (todos ADMIN):

- GET    /admin/providers              → lista providers (com ``last_synced_at`` e nº modelos)
- POST   /admin/providers/{id}/sync    → dispara sync do provider
- GET    /admin/models?tier&provider   → lista modelos com filtros
- PATCH  /admin/models/{id}            → edita ``tier`` ou ``active``
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.admin_ai_catalog_helpers import (
    AdminProviderCreate,
    AdminProviderModelCreate,
    AdminProviderOut,
    AdminProviderPatch,
    _normalise_provider_endpoint,
    create_manual_model,
    ensure_unique_provider_name,
    normalise_capabilities,
    set_default_capability,
)
from app.adapters.primary.http.admin_ai_catalog_sync import (
    supports_azure_foundry_sync,
    sync_azure_foundry_provider,
)
from app.adapters.primary.http.deps import require_role, require_super_admin
from app.adapters.primary.http.deps_base import get_db_session
from app.domain.entities import ModelTier, UserRole
from app.infrastructure.encryption import get_encryptor
from app.infrastructure.orm_models import AiModel, AiProvider
from app.schemas import AiModelOut, AiModelSyncResult

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)


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
            api_format=p.api_format,
            active=p.active,
            last_synced_at=p.last_synced_at.isoformat() if p.last_synced_at else None,
            models_count=int(counts.get(p.id, 0)),
        )
        for p in providers
    ]


@router.post(
    "/providers",
    response_model=AdminProviderOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_super_admin)],
)
async def create_provider(
    body: AdminProviderCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminProviderOut:
    await ensure_unique_provider_name(session, body.name)
    try:
        base_url, api_format = _normalise_provider_endpoint(body.base_url, body.api_format)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    provider = AiProvider(
        id=uuid.uuid4(),
        name=body.name,
        base_url=base_url,
        api_format=api_format,
        active=body.active,
        api_key_encrypted=get_encryptor().encrypt(body.api_key) if body.api_key else "",
    )
    session.add(provider)
    await session.flush()

    if body.model_id.strip():
        await create_manual_model(
            session,
            provider.id,
            AdminProviderModelCreate(
                model_id=body.model_id.strip(),
                display_name=body.display_name.strip() or body.model_id.strip(),
                context_window=body.context_window,
                is_default_text=body.is_default_text,
                is_default_embedding=body.is_default_embedding,
                capabilities=body.capabilities,
                active=True,
                tier=ModelTier.UNKNOWN,
            ),
        )

    await session.commit()
    await session.refresh(provider)
    return AdminProviderOut(
        id=provider.id,
        name=provider.name,
        base_url=provider.base_url,
        api_format=provider.api_format,
        active=provider.active,
        last_synced_at=provider.last_synced_at.isoformat() if provider.last_synced_at else None,
        models_count=1 if body.model_id.strip() else 0,
    )


@router.patch(
    "/providers/{provider_id}",
    response_model=AdminProviderOut,
    dependencies=[Depends(require_super_admin)],
)
async def patch_provider(
    provider_id: uuid.UUID,
    body: AdminProviderPatch,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminProviderOut:
    provider = await session.get(AiProvider, provider_id)
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider não encontrado.",
        )
    if body.name is not None and body.name != provider.name:
        await ensure_unique_provider_name(session, body.name, provider_id)
        provider.name = body.name
    if body.base_url is not None or body.api_format is not None:
        try:
            base_url, api_format = _normalise_provider_endpoint(
                body.base_url or provider.base_url,
                body.api_format or provider.api_format,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
            ) from exc
        provider.base_url = base_url
        provider.api_format = api_format
    if body.api_key:
        provider.api_key_encrypted = get_encryptor().encrypt(body.api_key)
    if body.active is not None:
        provider.active = body.active
    await session.commit()
    await session.refresh(provider)
    count = (
        await session.execute(
            select(func.count(AiModel.id)).where(AiModel.provider_id == provider.id)
        )
    ).scalar_one()
    return AdminProviderOut(
        id=provider.id,
        name=provider.name,
        base_url=provider.base_url,
        api_format=provider.api_format,
        active=provider.active,
        last_synced_at=provider.last_synced_at.isoformat() if provider.last_synced_at else None,
        models_count=int(count),
    )


@router.post(
    "/providers/{provider_id}/models",
    response_model=AiModelOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_super_admin)],
)
async def create_provider_model(
    provider_id: uuid.UUID,
    body: AdminProviderModelCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AiModelOut:
    provider = await session.get(AiProvider, provider_id)
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider não encontrado.",
        )
    model = await create_manual_model(session, provider_id, body)
    provider.last_synced_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(model)
    return AiModelOut.model_validate(model)


@router.post(
    "/providers/{provider_id}/sync",
    response_model=AiModelSyncResult,
    dependencies=[Depends(require_super_admin)],
)
async def sync_provider(
    provider_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AiModelSyncResult:
    """Dispara sync do provider."""
    provider = await session.get(AiProvider, provider_id)
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Provider não encontrado."
        )
    if provider.name == "OpenRouter":
        # Reutiliza o sync existente no router ``ai_models``.
        from app.adapters.primary.http.ai_models import sync_ai_models_from_openrouter

        return await sync_ai_models_from_openrouter(session)
    if supports_azure_foundry_sync(provider):
        return await sync_azure_foundry_provider(session, provider)
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"Sync para '{provider.name}' ainda não implementado.",
    )


class AdminModelFilter(BaseModel):
    provider_id: uuid.UUID | None = None
    tier: ModelTier | None = None
    only_active: bool = False
    include_inactive_providers: bool = False


@router.get("/models", response_model=list[AiModelOut])
async def list_models_admin(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    provider_id: uuid.UUID | None = None,
    tier: ModelTier | None = None,
    only_active: bool = False,
    include_inactive_providers: bool = False,
) -> list[AiModelOut]:
    """Lista admin com filtros opcionais (sem filtro por user — ADMIN vê tudo).

    Por padrão, o catálogo operacional mostra apenas modelos de providers ativos.
    Providers inativos permanecem no banco como histórico/cache, mas não devem
    poluir a tela nem aparecer em seletores operacionais.
    """
    stmt = select(AiModel).join(AiProvider, AiProvider.id == AiModel.provider_id)
    stmt = stmt.order_by(AiProvider.name, AiModel.display_name)
    if not include_inactive_providers:
        stmt = stmt.where(AiProvider.active.is_(True))
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
    capabilities: list[str] | None = None
    is_default_text: bool | None = None
    is_default_embedding: bool | None = None


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
    if body.capabilities is not None:
        try:
            model.capabilities = normalise_capabilities(body.capabilities)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        flags = dict(model.is_default or {})
        for capability in list(flags):
            if capability not in model.capabilities:
                flags.pop(capability, None)
        model.is_default = flags
    if body.is_default_text is not None:
        if body.is_default_text and "text" not in model.capabilities:
            model.capabilities = ["text", *model.capabilities]
        await set_default_capability(session, model, "text", body.is_default_text)
    if body.is_default_embedding is not None:
        if body.is_default_embedding and "embedding" not in model.capabilities:
            model.capabilities = [*model.capabilities, "embedding"]
        await set_default_capability(session, model, "embedding", body.is_default_embedding)
    await session.commit()
    await session.refresh(model)
    return AiModelOut.model_validate(model)
