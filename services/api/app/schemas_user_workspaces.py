"""Schemas for per-user repository workspaces."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class UserWorkspaceEnsureBody(BaseModel):
    repository_id: uuid.UUID
    base_branch: str | None = Field(default=None, max_length=256)


class UserWorkspaceOut(BaseModel):
    id: uuid.UUID
    repository_id: uuid.UUID
    sandbox_id: uuid.UUID | None = None
    sandbox_key: str
    base_branch: str
    workspace_path: str
    status: str
    health_message: str = ""
    last_prepared_at: datetime | None = None
    last_used_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
