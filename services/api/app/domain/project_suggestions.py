"""Domain objects for project-aware chat suggestions."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SuggestionCategory(StrEnum):
    EXPLORE = "explore"
    BUILD = "build"
    REVIEW = "review"
    FIX = "fix"
    SUPPORT = "support"


class SuggestionSource(StrEnum):
    INITIAL_CONTEXT = "initial_context"
    QUESTION_HISTORY = "question_history"
    FALLBACK = "fallback"


class SuggestionStatus(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    SUPPRESSED = "suppressed"
    STALE = "stale"


class SuggestionSafetyState(StrEnum):
    SAFE = "safe"
    NEEDS_REVIEW = "needs_review"
    BLOCKED = "blocked"


class SuggestionFreshnessState(StrEnum):
    FRESH = "fresh"
    AGING = "aging"
    STALE = "stale"


class CalibrationTrigger(StrEnum):
    INITIAL_CONTEXT = "initial_context"
    QUESTION_HISTORY = "question_history"
    DOCUMENT_CHANGED = "document_changed"
    SKILL_CHANGED = "skill_changed"
    DAILY = "daily"
    MANUAL = "manual"


class CalibrationStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ProjectSuggestion:
    id: uuid.UUID
    repository_id: uuid.UUID
    title: str
    prompt: str
    category: SuggestionCategory
    source: SuggestionSource
    status: SuggestionStatus = SuggestionStatus.ACTIVE
    priority: int = 100
    safety_state: SuggestionSafetyState = SuggestionSafetyState.SAFE
    freshness_state: SuggestionFreshnessState = SuggestionFreshnessState.FRESH
    analysis_window_start: datetime | None = None
    analysis_window_end: datetime | None = None
    last_calibrated_at: datetime | None = None
    suppressed_at: datetime | None = None
    suppressed_by: uuid.UUID | None = None
    suppression_reason: str | None = None
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)


@dataclass
class ProjectSuggestionProfile:
    repository_id: uuid.UUID
    repo_slug: str
    repo_name: str
    default_branch: str
    documents: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)


@dataclass
class ProjectQuestionSignal:
    category: SuggestionCategory
    count: int
    sample_prompt: str


@dataclass
class SuggestionCalibrationRun:
    id: uuid.UUID
    repository_id: uuid.UUID
    trigger: CalibrationTrigger
    status: CalibrationStatus = CalibrationStatus.QUEUED
    started_at: datetime | None = None
    finished_at: datetime | None = None
    analysis_window_start: datetime | None = None
    analysis_window_end: datetime | None = None
    eligible_message_count: int = 0
    eligible_user_count: int = 0
    suggestions_created: int = 0
    suggestions_activated: int = 0
    suggestions_suppressed: int = 0
    failure_reason: str | None = None
    created_at: datetime = field(default_factory=_utcnow)
