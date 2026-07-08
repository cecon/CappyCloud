"""Pydantic schemas for platform control plane HTTP contracts."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.domain.entities import ModelTier

_CONFLUENCE_LABEL_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")


def _normalise_confluence_labels(value: object) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        raw_items = value.split(",")
    elif isinstance(value, list):
        raw_items = value
    else:
        raise ValueError("Rótulos do Confluence devem ser uma lista ou texto separado por vírgula.")

    labels: list[str] = []
    seen: set[str] = set()
    for raw in raw_items:
        label = str(raw).strip().lower()
        if not label:
            continue
        if not _CONFLUENCE_LABEL_RE.match(label):
            raise ValueError(
                "Rótulo Confluence inválido. Use letras minúsculas, números, ponto, "
                "hífen ou underscore."
            )
        if label not in seen:
            seen.add(label)
            labels.append(label)
    return labels


class GitProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    provider_type: str = Field(default="github", max_length=32)
    base_url: str = Field(default="", max_length=2048)
    org_or_project: str = Field(default="", max_length=512)
    token: str = Field(default="", description="PAT em texto plano — será criptografado")


class GitProviderOut(BaseModel):
    id: uuid.UUID
    name: str
    provider_type: str
    base_url: str
    org_or_project: str
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AiProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    base_url: str = Field(default="https://openrouter.ai/api/v1", max_length=2048)
    api_format: str = Field(default="chat_completions", max_length=32)
    api_key: str = Field(default="", description="API key em texto plano — será criptografada")


class AiProviderOut(BaseModel):
    id: uuid.UUID
    name: str
    base_url: str
    api_format: str = "chat_completions"
    active: bool
    last_synced_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AiModelCreate(BaseModel):
    provider_id: uuid.UUID
    model_id: str = Field(min_length=1, max_length=256)
    display_name: str = Field(min_length=1, max_length=256)
    capabilities: list[str] = Field(default_factory=lambda: ["text"])
    is_default: dict = Field(default_factory=dict)
    context_window: int = Field(default=200000, ge=1)
    input_cost_per_1m_usd: float | None = None
    output_cost_per_1m_usd: float | None = None


class AiModelOut(BaseModel):
    id: uuid.UUID
    provider_id: uuid.UUID
    model_id: str
    display_name: str
    capabilities: list[str]
    is_default: dict
    context_window: int
    input_cost_per_1m_usd: float | None = None
    output_cost_per_1m_usd: float | None = None
    tier: ModelTier = ModelTier.UNKNOWN
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AiModelSyncResult(BaseModel):
    """Resultado de um sync de catálogo de modelos → DB."""

    provider_id: uuid.UUID
    fetched: int
    created: int
    updated: int
    deactivated: int


class RepositoryCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=128)
    name: str = Field(min_length=1, max_length=256)
    clone_url: str = Field(min_length=1, max_length=2048)
    default_branch: str = Field(default="main", max_length=256)
    confluence_url: str = Field(default="", max_length=2048)
    confluence_space: str = Field(default="", max_length=128)
    confluence_labels: list[str] = Field(default_factory=list, max_length=32)
    provider_id: uuid.UUID | None = None
    sandbox_id: uuid.UUID | None = None
    pat_token: str | None = Field(default=None, max_length=4096)
    provider_type: str | None = Field(default=None, max_length=32)
    signoz_service_name: str | None = Field(default=None, max_length=256)

    @field_validator("confluence_labels", mode="before")
    @classmethod
    def confluence_labels_lista(cls, v: object) -> list[str]:
        return _normalise_confluence_labels(v)


class RepositoryOut(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    clone_url: str
    default_branch: str
    confluence_url: str = ""
    confluence_space: str = ""
    confluence_labels: list[str] = Field(default_factory=list)
    provider_id: uuid.UUID | None = None
    sandbox_id: uuid.UUID | None = None
    sandbox_status: str
    sandbox_path: str
    last_sync_at: datetime | None = None
    error_message: str | None = None
    signoz_service_name: str | None = None
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
