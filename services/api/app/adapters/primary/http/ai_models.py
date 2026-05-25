"""AI Providers & Models HTTP router — catálogo de modelos e chaves de API."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import (
    get_authenticated_user,
    get_db_session,
    require_super_admin,
)
from app.adapters.secondary.persistence.sqlalchemy_user_access_repo import (
    SQLAlchemyUserAiModelAccessRepository,
)
from app.domain.entities import ModelTier, User, UserRole
from app.infrastructure.encryption import get_encryptor
from app.infrastructure.openrouter_models import fetch_openrouter_models, filter_text_entries
from app.infrastructure.orm_models import AiModel, AiProvider
from app.schemas import (
    AiModelCreate,
    AiModelOut,
    AiModelSyncResult,
    AiProviderCreate,
    AiProviderOut,
)

log = logging.getLogger(__name__)
router = APIRouter(tags=["ai"])
_OPENROUTER_PROVIDER_NAME = "OpenRouter"
_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_DEFAULT_FREE_TEXT_MODEL_ID = "openai/gpt-oss-120b:free"


def _active_text_model_filter():
    return and_(
        AiModel.active == True,  # noqa: E712
        text("ai_models.capabilities ? 'text'"),
    )


def _derive_tier(input_cost: float | None, output_cost: float | None) -> str:
    """Deriva ``tier`` do par de preços (ADR-006 §6).

    - Ambos zero → ``free``.
    - Qualquer > 0 → ``paid``.
    - Sem dados → ``unknown`` (fallback defensivo).
    """
    if input_cost is None and output_cost is None:
        return ModelTier.UNKNOWN.value
    if (input_cost or 0.0) == 0.0 and (output_cost or 0.0) == 0.0:
        return ModelTier.FREE.value
    return ModelTier.PAID.value


def _text_default_flags(model_id: str, current: dict | None = None) -> dict:
    flags = dict(current or {})
    if model_id == _DEFAULT_FREE_TEXT_MODEL_ID:
        flags["text"] = True
    else:
        flags.pop("text", None)
    return flags


# ── AI Providers ──────────────────────────────────────────────


@router.get("/ai-providers", response_model=list[AiProviderOut])
async def list_ai_providers(
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[AiProviderOut]:
    rows = await session.execute(select(AiProvider).order_by(AiProvider.name))
    return [AiProviderOut.model_validate(r) for r in rows.scalars()]


@router.post(
    "/ai-providers",
    response_model=AiProviderOut,
    status_code=201,
    dependencies=[Depends(require_super_admin)],
)
async def create_ai_provider(
    body: AiProviderCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AiProviderOut:
    enc = get_encryptor()
    provider = AiProvider(
        id=uuid.uuid4(),
        name=body.name,
        base_url=body.base_url,
        api_format=body.api_format,
        api_key_encrypted=enc.encrypt(body.api_key) if body.api_key else "",
    )
    session.add(provider)
    await session.commit()
    await session.refresh(provider)
    return AiProviderOut.model_validate(provider)


@router.patch(
    "/ai-providers/{provider_id}/key",
    response_model=AiProviderOut,
    dependencies=[Depends(require_super_admin)],
)
async def update_ai_provider_key(
    provider_id: uuid.UUID,
    api_key: str,
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
    current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[AiModelOut]:
    """Lista modelos ativos disponíveis ao utilizador (ADR-005 §5).

    - ADMIN vê todos os modelos ativos (filtra apenas por capability ``text``).
    - USER vê apenas modelos para os quais tem ``UserAiModelAccess``.
    """
    stmt = (
        select(AiModel)
        .join(AiProvider)
        .where(_active_text_model_filter())
        .where(AiProvider.active.is_(True))
        .order_by(AiModel.display_name)
    )
    if current.role is not UserRole.ADMIN:
        allowed = await SQLAlchemyUserAiModelAccessRepository(session).list_resources_for_user(
            current.id
        )
        if not allowed:
            return []
        stmt = stmt.where(AiModel.id.in_(allowed))
    rows = await session.execute(stmt)
    return [AiModelOut.model_validate(r) for r in rows.scalars()]


@router.post(
    "/ai-models",
    response_model=AiModelOut,
    status_code=201,
    dependencies=[Depends(require_super_admin)],
)
async def create_ai_model(
    body: AiModelCreate,
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
        input_cost_per_1m_usd=body.input_cost_per_1m_usd,
        output_cost_per_1m_usd=body.output_cost_per_1m_usd,
    )
    session.add(model)
    await session.commit()
    await session.refresh(model)
    return AiModelOut.model_validate(model)


@router.delete(
    "/ai-models/{model_id}",
    status_code=204,
    dependencies=[Depends(require_super_admin)],
)
async def delete_ai_model(
    model_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    model = await session.get(AiModel, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Modelo não encontrado")
    await session.delete(model)
    await session.commit()


@router.post(
    "/ai-models/sync-from-openrouter",
    response_model=AiModelSyncResult,
    dependencies=[Depends(require_super_admin)],
)
async def sync_ai_models_from_openrouter(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AiModelSyncResult:
    """Sincroniza catálogo do OpenRouter com a tabela ``ai_models``.

    Comportamento:
    - Garante a existência do provider ``OpenRouter``.
    - Faz upsert por ``(provider_id, model_id)``: cria novos, actualiza
      preço/contexto/capabilities dos existentes.
    - Marca como ``active=False`` modelos que já não constam do catálogo
      (não os apaga, para preservar FK em ``conversations.ai_model_id``).
    """
    provider = (
        await session.execute(
            select(AiProvider).where(AiProvider.name == _OPENROUTER_PROVIDER_NAME)
        )
    ).scalar_one_or_none()
    if provider is None:
        provider = AiProvider(
            id=uuid.uuid4(),
            name=_OPENROUTER_PROVIDER_NAME,
            base_url=_OPENROUTER_BASE_URL,
            api_key_encrypted="",
        )
        session.add(provider)
        await session.flush()

    try:
        catalog = filter_text_entries(await fetch_openrouter_models())
    except Exception as exc:
        log.exception("Falha ao buscar catálogo OpenRouter")
        raise HTTPException(status_code=502, detail=f"OpenRouter indisponível: {exc}") from exc

    existing = (
        (await session.execute(select(AiModel).where(AiModel.provider_id == provider.id)))
        .scalars()
        .all()
    )
    existing_by_model_id = {m.model_id: m for m in existing}
    fetched_ids: set[str] = set()
    created = 0
    updated = 0
    for entry in catalog:
        fetched_ids.add(entry["model_id"])
        current = existing_by_model_id.get(entry["model_id"])
        input_raw = entry["input_cost_per_1m_usd"]
        output_raw = entry["output_cost_per_1m_usd"]
        # Mantemos Decimal (precisão exata), mas anotamos como float | None
        # porque é o que o Mapped declara — o SQLAlchemy aceita ambos via
        # Numeric() column. Esta cast é puramente para o type-checker.
        input_cost = float(Decimal(str(input_raw))) if input_raw is not None else None
        output_cost = float(Decimal(str(output_raw))) if output_raw is not None else None
        tier = _derive_tier(input_cost, output_cost)
        if current is None:
            session.add(
                AiModel(
                    id=uuid.uuid4(),
                    provider_id=provider.id,
                    model_id=entry["model_id"],
                    display_name=entry["display_name"],
                    capabilities=entry["capabilities"],
                    is_default=_text_default_flags(entry["model_id"]),
                    context_window=entry["context_window"],
                    input_cost_per_1m_usd=input_cost,
                    output_cost_per_1m_usd=output_cost,
                    tier=tier,
                    active=tier == ModelTier.FREE.value,
                )
            )
            created += 1
        else:
            current.display_name = entry["display_name"]
            current.context_window = entry["context_window"]
            current.capabilities = entry["capabilities"]
            current.input_cost_per_1m_usd = input_cost
            current.output_cost_per_1m_usd = output_cost
            current.is_default = _text_default_flags(entry["model_id"], current.is_default)
            current.tier = tier
            updated += 1

    stale_ids = [m.id for m in existing if m.model_id not in fetched_ids and m.active]
    if stale_ids:
        await session.execute(update(AiModel).where(AiModel.id.in_(stale_ids)).values(active=False))

    # Bump last_synced_at no provider (ADR-006 §5).
    provider.last_synced_at = datetime.now(UTC)
    await session.commit()
    return AiModelSyncResult(
        provider_id=provider.id,
        fetched=len(catalog),
        created=created,
        updated=updated,
        deactivated=len(stale_ids),
    )
