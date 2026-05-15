"""Pydantic schemas para Skills (knowledge base)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# ── Skills ─────────────────────────────────────────────────────


class SkillCreate(BaseModel):
    repository_id: uuid.UUID
    title: str = Field(min_length=1, max_length=512)
    slug: str | None = Field(default=None, max_length=256)
    summary: str = Field(default="", max_length=2048)
    content: str | None = Field(default=None, max_length=500_000)
    tags: list[str] = Field(default_factory=list)
    source_url: str | None = Field(default=None, max_length=2048)


class SkillUpdate(BaseModel):
    repository_id: uuid.UUID | None = None
    title: str | None = Field(default=None, max_length=512)
    summary: str | None = Field(default=None, max_length=2048)
    content: str | None = Field(default=None, max_length=500_000)
    tags: list[str] | None = None
    source_url: str | None = Field(default=None, max_length=2048)
    active: bool | None = None


class SkillOut(BaseModel):
    id: uuid.UUID
    repository_id: uuid.UUID | None = None
    slug: str
    title: str
    summary: str
    content: str
    tags: list[str] = Field(default_factory=list)
    source_url: str | None = None
    active: bool
    has_embedding: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SkillSearchResult(BaseModel):
    """Resultado simplificado de busca (não retorna content completo por padrão)."""

    id: uuid.UUID
    slug: str
    title: str
    summary: str
    score: float
    source_url: str | None = None


class SkillImportFromUrlBody(BaseModel):
    url: str = Field(min_length=4, max_length=2048)
    tags: list[str] = Field(default_factory=list)
