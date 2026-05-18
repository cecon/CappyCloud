"""Esquemas Pydantic para MCP Servers."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

_MCP_NAME_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")


class McpServerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    command: str = Field(min_length=1, max_length=256)
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def name_valido(cls, v: str) -> str:
        if not _MCP_NAME_RE.match(v):
            raise ValueError(
                "Nome de MCP inválido. Use apenas letras, números, hífens e sublinhados."
            )
        return v


class McpServerUpdate(McpServerCreate):
    """Mesmo payload de criação — todos os campos são obrigatórios na atualização."""


class McpServerOut(BaseModel):
    id: uuid.UUID
    sandbox_id: uuid.UUID
    name: str
    command: str
    args: list[str]
    env: dict[str, str]
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
