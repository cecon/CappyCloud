"""Esquemas Pydantic para skills e agents globais por sandbox (ADR-004 §6)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# Nome canônico (vira pasta/arquivo no container) — alfanum + underscore + hífen.
_GLOBAL_NAME_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")


def _validate_name(v: str) -> str:
    if not _GLOBAL_NAME_RE.match(v):
        raise ValueError("Nome inválido. Use apenas letras, números, hífens e sublinhados (1-64).")
    return v


# ── SandboxSkill ─────────────────────────────────────────────────────────────


class SandboxSkillCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str = ""
    content: str = ""
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def name_valido(cls, v: str) -> str:
        return _validate_name(v)


class SandboxSkillUpdate(SandboxSkillCreate):
    """Mesmo payload — todos os campos obrigatórios na atualização."""


class SandboxSkillOut(BaseModel):
    id: uuid.UUID
    sandbox_id: uuid.UUID
    name: str
    description: str
    content: str
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── SandboxAgent ─────────────────────────────────────────────────────────────


class SandboxAgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str = ""
    system_prompt: str = ""
    model: str = Field(default="", max_length=256)
    tools: list[str] = Field(default_factory=list)
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def name_valido(cls, v: str) -> str:
        return _validate_name(v)


class SandboxAgentUpdate(SandboxAgentCreate):
    """Mesmo payload — todos os campos obrigatórios na atualização."""


class SandboxAgentOut(BaseModel):
    id: uuid.UUID
    sandbox_id: uuid.UUID
    name: str
    description: str
    system_prompt: str
    model: str
    tools: list[str]
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
