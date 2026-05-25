"""Helpers for the admin LLM catalog HTTP router."""

from __future__ import annotations

import uuid
from urllib.parse import urlsplit, urlunsplit

from fastapi import HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import ModelTier
from app.infrastructure.azure_foundry_models import is_azure_foundry_endpoint
from app.infrastructure.orm_models import AiModel, AiProvider

_SUPPORTED_API_FORMATS = {"chat_completions", "responses"}
_SUPPORTED_CAPABILITIES = {"text", "vision", "embedding", "audio", "video", "image"}


def _normalise_api_format(value: str | None) -> str:
    raw = (value or "chat_completions").strip().lower()
    if raw not in _SUPPORTED_API_FORMATS:
        raise ValueError("Formato de API deve ser chat_completions ou responses.")
    return raw


def _normalise_provider_endpoint(
    raw_url: str,
    explicit_api_format: str | None = None,
) -> tuple[str, str]:
    """Aceita URL base ou endpoint final e devolve (base_url, api_format)."""
    raw = raw_url.strip()
    if not raw:
        raise ValueError("Base URL é obrigatória.")
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Base URL deve começar com http:// ou https://.")

    path = parsed.path.rstrip("/")
    lower_path = path.lower()
    inferred = _normalise_api_format(explicit_api_format)
    if lower_path.endswith("/responses"):
        path = path[: -len("/responses")]
        inferred = "responses"
    elif lower_path.endswith("/chat/completions"):
        path = path[: -len("/chat/completions")]
        inferred = "chat_completions"

    if not path and is_azure_foundry_endpoint(raw):
        path = "/openai/v1"

    base_url = urlunsplit((parsed.scheme, parsed.netloc, path.rstrip("/"), "", ""))
    return base_url, inferred


class AdminProviderOut(BaseModel):
    id: uuid.UUID
    name: str
    base_url: str
    api_format: str = "chat_completions"
    active: bool
    last_synced_at: str | None = None
    models_count: int = 0


class AdminProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    base_url: str = Field(min_length=1, max_length=2048)
    api_format: str = Field(default="chat_completions", max_length=32)
    api_key: str = Field(default="", max_length=4096)
    model_id: str = Field(default="", max_length=256)
    display_name: str = Field(default="", max_length=256)
    context_window: int = Field(default=200000, ge=1)
    active: bool = True
    is_default_text: bool = False
    is_default_embedding: bool = False
    capabilities: list[str] = Field(default_factory=lambda: ["text"])

    @field_validator("api_format")
    @classmethod
    def api_format_valido(cls, value: str) -> str:
        return _normalise_api_format(value)

    @field_validator("capabilities")
    @classmethod
    def capabilities_validas(cls, value: list[str]) -> list[str]:
        return normalise_capabilities(value)


class AdminProviderPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    base_url: str | None = Field(default=None, min_length=1, max_length=2048)
    api_format: str | None = Field(default=None, max_length=32)
    api_key: str | None = Field(default=None, max_length=4096)
    active: bool | None = None

    @field_validator("api_format")
    @classmethod
    def api_format_valido(cls, value: str | None) -> str | None:
        return _normalise_api_format(value) if value is not None else None


class AdminProviderModelCreate(BaseModel):
    model_id: str = Field(min_length=1, max_length=256)
    display_name: str = Field(default="", max_length=256)
    capabilities: list[str] = Field(default_factory=lambda: ["text"])
    is_default_text: bool = False
    is_default_embedding: bool = False
    context_window: int = Field(default=200000, ge=1)
    tier: ModelTier = ModelTier.UNKNOWN
    active: bool = True
    input_cost_per_1m_usd: float | None = None
    output_cost_per_1m_usd: float | None = None

    @field_validator("capabilities")
    @classmethod
    def capabilities_validas(cls, value: list[str]) -> list[str]:
        return normalise_capabilities(value)


async def ensure_unique_provider_name(
    session: AsyncSession, name: str, provider_id: uuid.UUID | None = None
) -> None:
    stmt = select(AiProvider).where(AiProvider.name == name)
    if provider_id is not None:
        stmt = stmt.where(AiProvider.id != provider_id)
    exists = (await session.execute(stmt.limit(1))).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe um provider LLM com esse nome.",
        )


def normalise_capabilities(value: list[str] | None) -> list[str]:
    capabilities: list[str] = []
    seen: set[str] = set()
    for item in value or ["text"]:
        capability = str(item).strip().lower()
        if not capability:
            continue
        if capability not in _SUPPORTED_CAPABILITIES:
            raise ValueError(
                "Capability inválida. Use text, vision, embedding, audio, video ou image."
            )
        if capability not in seen:
            seen.add(capability)
            capabilities.append(capability)
    if not capabilities:
        raise ValueError("Modelo precisa ter ao menos uma capability.")
    return capabilities


async def set_default_capability(
    session: AsyncSession,
    model: AiModel,
    capability: str,
    enabled: bool,
) -> None:
    flags = dict(model.is_default or {})
    if enabled:
        rows = (await session.execute(select(AiModel))).scalars().all()
        for current in rows:
            current_flags = dict(current.is_default or {})
            if current_flags.pop(capability, None) is not None:
                current.is_default = current_flags
        flags[capability] = True
    else:
        flags.pop(capability, None)
    model.is_default = flags


async def create_manual_model(
    session: AsyncSession,
    provider_id: uuid.UUID,
    body: AdminProviderModelCreate,
) -> AiModel:
    existing = (
        await session.execute(
            select(AiModel).where(
                AiModel.provider_id == provider_id,
                AiModel.model_id == body.model_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esse modelo já existe para o provider.",
        )
    capabilities = normalise_capabilities(body.capabilities)
    if body.is_default_text and "text" not in capabilities:
        capabilities = ["text", *capabilities]
    if body.is_default_embedding and "embedding" not in capabilities:
        capabilities = [*capabilities, "embedding"]
    is_default: dict[str, bool] = {}
    if body.is_default_text:
        is_default["text"] = True
    if body.is_default_embedding:
        is_default["embedding"] = True
    model = AiModel(
        id=uuid.uuid4(),
        provider_id=provider_id,
        model_id=body.model_id,
        display_name=body.display_name or body.model_id,
        capabilities=capabilities,
        is_default=is_default,
        context_window=body.context_window,
        input_cost_per_1m_usd=body.input_cost_per_1m_usd,
        output_cost_per_1m_usd=body.output_cost_per_1m_usd,
        tier=body.tier.value,
        active=body.active,
    )
    session.add(model)
    if body.is_default_text:
        await set_default_capability(session, model, "text", True)
    if body.is_default_embedding:
        await set_default_capability(session, model, "embedding", True)
    return model
