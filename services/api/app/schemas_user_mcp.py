"""Pydantic schemas for user-facing repository MCP servers."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

_NAME_RE = re.compile(r"^[a-zA-Z0-9_. -]{1,96}$")


class UserMcpServerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=96)
    repository_id: uuid.UUID
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        if not _NAME_RE.match(value.strip()):
            raise ValueError(
                "Nome inválido. Use letras, números, espaço, ponto, hífen e sublinhado."
            )
        return value.strip()


class UserMcpServerUpdate(UserMcpServerCreate):
    """Atualização completa do MCP HTTP."""


class UserMcpServerOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    repository_id: uuid.UUID
    name: str
    token_preview: str
    enabled: bool
    created_at: datetime
    updated_at: datetime
    last_used_at: datetime | None = None

    model_config = {"from_attributes": True}


class UserMcpServerSecretOut(UserMcpServerOut):
    token: str
