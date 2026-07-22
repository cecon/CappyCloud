"""Pydantic schemas for project-aware chat suggestions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProjectSuggestionCardOut(BaseModel):
    id: uuid.UUID
    title: str
    prompt: str
    category: str
    source: str
    freshness_state: str


class ProjectSuggestionsDiagnosticOut(BaseModel):
    using_initial_context: bool
    reason: str


class ProjectSuggestionsOut(BaseModel):
    repo_slug: str
    repo_name: str
    state: Literal["calibrated", "initial", "fallback", "empty", "error"]
    last_calibrated_at: datetime | None
    cards: list[ProjectSuggestionCardOut]
    diagnostic: ProjectSuggestionsDiagnosticOut


class ProjectSuggestionRecalibrateBody(BaseModel):
    trigger: Literal["manual"] = "manual"
    force: bool = False


class ProjectSuggestionPatchBody(BaseModel):
    status: Literal["active", "suppressed"]
    reason: str | None = Field(default=None, max_length=200)


class ProjectSuggestionRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    repository_id: uuid.UUID
    trigger: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    eligible_message_count: int = 0
    eligible_user_count: int = 0
    suggestions_created: int = 0
    suggestions_activated: int = 0
    suggestions_suppressed: int = 0
    failure_reason: str | None = None


class ProjectSuggestionStatusOut(BaseModel):
    repository_id: uuid.UUID
    counts: dict[str, int]
    last_run: ProjectSuggestionRunOut | None


class ProjectSuggestionPatchOut(BaseModel):
    id: uuid.UUID
    status: str
    suppressed_at: datetime | None
