"""Provider sync helpers for the admin LLM catalog router."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import ModelTier
from app.infrastructure.azure_foundry_models import (
    AzureFoundryDeployment,
    fetch_azure_foundry_deployments,
    is_azure_foundry_endpoint,
)
from app.infrastructure.encryption import get_encryptor
from app.infrastructure.orm_models import AiModel, AiProvider
from app.schemas import AiModelSyncResult


def supports_azure_foundry_sync(provider: AiProvider) -> bool:
    return is_azure_foundry_endpoint(provider.base_url) or "azure" in provider.name.lower()


async def sync_azure_foundry_provider(
    session: AsyncSession,
    provider: AiProvider,
) -> AiModelSyncResult:
    api_key = _decrypt_provider_key(provider)
    if not api_key:
        raise HTTPException(
            status_code=422,
            detail="Provider Azure Foundry precisa de uma API key para sincronizar deployments.",
        )
    try:
        catalog = await fetch_azure_foundry_deployments(
            base_url=provider.base_url,
            api_key=api_key,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Azure Foundry indisponível para sync: {exc}",
        ) from exc

    return await upsert_provider_models(
        session,
        provider,
        catalog,
        default_active=True,
        tier=ModelTier.UNKNOWN.value,
    )


async def upsert_provider_models(
    session: AsyncSession,
    provider: AiProvider,
    catalog: list[AzureFoundryDeployment],
    *,
    default_active: bool,
    tier: str,
) -> AiModelSyncResult:
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
        if current is None:
            session.add(
                AiModel(
                    id=uuid.uuid4(),
                    provider_id=provider.id,
                    model_id=entry["model_id"],
                    display_name=entry["display_name"],
                    capabilities=entry["capabilities"],
                    is_default={},
                    context_window=entry["context_window"],
                    input_cost_per_1m_usd=entry["input_cost_per_1m_usd"],
                    output_cost_per_1m_usd=entry["output_cost_per_1m_usd"],
                    tier=tier,
                    active=default_active,
                )
            )
            created += 1
        else:
            current.display_name = entry["display_name"]
            current.context_window = entry["context_window"]
            current.capabilities = entry["capabilities"]
            current.input_cost_per_1m_usd = entry["input_cost_per_1m_usd"]
            current.output_cost_per_1m_usd = entry["output_cost_per_1m_usd"]
            current.tier = tier
            current.active = True
            updated += 1

    stale_ids = [m.id for m in existing if m.model_id not in fetched_ids and m.active]
    if stale_ids:
        await session.execute(update(AiModel).where(AiModel.id.in_(stale_ids)).values(active=False))

    provider.last_synced_at = datetime.now(UTC)
    await session.commit()
    return AiModelSyncResult(
        provider_id=provider.id,
        fetched=len(catalog),
        created=created,
        updated=updated,
        deactivated=len(stale_ids),
    )


def _decrypt_provider_key(provider: AiProvider) -> str:
    ciphertext = provider.api_key_encrypted or ""
    if not ciphertext:
        return ""
    return get_encryptor().decrypt(ciphertext)
