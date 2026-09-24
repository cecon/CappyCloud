"""Schemas HTTP de workspaces (admin, super admin)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]{1,62}$"
ALIAS_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"


class WorkspaceRepositoryIn(BaseModel):
    repository_id: uuid.UUID
    # Vazio = slug do repositório.
    alias: str | None = Field(default=None, pattern=ALIAS_PATTERN)
    # Vazio = default_branch do repositório.
    base_branch: str = Field(default="", max_length=256)
    # Somente leitura: o agente consulta, mas não edita (sem PR).
    read_only: bool = False


class WorkspaceCreate(BaseModel):
    slug: str = Field(pattern=SLUG_PATTERN)
    name: str = Field(min_length=1, max_length=256)
    sandbox_id: uuid.UUID
    claude_md: str = Field(default="", max_length=50000)
    repositories: list[WorkspaceRepositoryIn] = Field(default_factory=list)


class WorkspaceUpdate(BaseModel):
    """``slug`` e ``sandbox_id`` são imutáveis: definem a pasta no sandbox."""

    name: str | None = Field(default=None, min_length=1, max_length=256)
    claude_md: str | None = Field(default=None, max_length=50000)
    active: bool | None = None
    repositories: list[WorkspaceRepositoryIn] | None = None


class WorkspaceRepositoryOut(BaseModel):
    repository_id: uuid.UUID
    slug: str
    name: str
    alias: str
    base_branch: str
    default_branch: str
    sandbox_status: str
    read_only: bool = False


class WorkspaceOut(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    sandbox_id: uuid.UUID
    claude_md: str
    active: bool
    sync_status: str
    sync_error: str | None
    last_sync_at: datetime | None
    created_at: datetime
    repositories: list[WorkspaceRepositoryOut]
