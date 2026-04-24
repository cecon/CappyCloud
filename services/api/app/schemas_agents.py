"""Pydantic schemas para Agentes (perfis) e Skills (knowledge base)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# ── Agents ─────────────────────────────────────────────────────


class AgentCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=128, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=1, max_length=256)
    description: str = Field(default="", max_length=4096)
    icon: str = Field(default="support_agent", max_length=64)
    system_prompt: str = Field(default="", max_length=100_000)
    default_model: str | None = Field(default=None, max_length=256)
    active: bool = True
    is_private: bool = False
    is_default: bool = False


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=256)
    description: str | None = Field(default=None, max_length=4096)
    icon: str | None = Field(default=None, max_length=64)
    system_prompt: str | None = Field(default=None, max_length=100_000)
    default_model: str | None = Field(default=None, max_length=256)
    active: bool | None = None
    is_private: bool | None = None
    is_default: bool | None = None


class AgentOut(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    description: str
    icon: str
    system_prompt: str
    default_model: str | None = None
    active: bool
    is_private: bool = False
    is_default: bool = False
    skills_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Skills ─────────────────────────────────────────────────────


class SkillCreate(BaseModel):
    agent_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=512)
    slug: str | None = Field(default=None, max_length=256)
    summary: str = Field(default="", max_length=2048)
    content: str = Field(min_length=1, max_length=500_000)
    tags: list[str] = Field(default_factory=list)
    source_url: str | None = Field(default=None, max_length=2048)


class SkillUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=512)
    summary: str | None = Field(default=None, max_length=2048)
    content: str | None = Field(default=None, max_length=500_000)
    tags: list[str] | None = None
    source_url: str | None = Field(default=None, max_length=2048)
    active: bool | None = None
    agent_id: uuid.UUID | None = None


class SkillOut(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID | None = None
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
    agent_id: uuid.UUID | None = None
    tags: list[str] = Field(default_factory=list)
