"""Ports for project-aware chat suggestion generation and persistence."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.domain.project_suggestions import (
    CalibrationTrigger,
    ProjectQuestionSignal,
    ProjectSuggestion,
    ProjectSuggestionProfile,
    SuggestionCalibrationRun,
    SuggestionStatus,
)


class ProjectSuggestionRepository(ABC):
    @abstractmethod
    async def list_active(self, repository_id: uuid.UUID, limit: int) -> list[ProjectSuggestion]:
        """Return safe active suggestions ordered for display."""

    @abstractmethod
    async def save_suggestions(
        self,
        repository_id: uuid.UUID,
        suggestions: list[ProjectSuggestion],
        *,
        replace_source: str | None = None,
    ) -> list[ProjectSuggestion]:
        """Persist suggestions and optionally stale previous rows from one source."""

    @abstractmethod
    async def get_profile(self, repository_id: uuid.UUID) -> ProjectSuggestionProfile | None:
        """Load project metadata, indexed documents, and registered skills."""

    @abstractmethod
    async def list_question_signals(
        self,
        repository_id: uuid.UUID,
        repo_slug: str,
    ) -> tuple[list[ProjectQuestionSignal], int, int]:
        """Return aggregated anonymized user-message patterns for the project."""

    @abstractmethod
    async def create_run(
        self,
        repository_id: uuid.UUID,
        trigger: CalibrationTrigger,
    ) -> SuggestionCalibrationRun:
        """Create a calibration run record."""

    @abstractmethod
    async def finish_run(self, run: SuggestionCalibrationRun) -> SuggestionCalibrationRun:
        """Persist final calibration run counters and status."""

    @abstractmethod
    async def latest_run(self, repository_id: uuid.UUID) -> SuggestionCalibrationRun | None:
        """Return the latest calibration run for a project."""

    @abstractmethod
    async def status_counts(self, repository_id: uuid.UUID) -> dict[SuggestionStatus, int]:
        """Return suggestion counts grouped by status."""

    @abstractmethod
    async def get_suggestion(self, suggestion_id: uuid.UUID) -> ProjectSuggestion | None:
        """Load one suggestion."""

    @abstractmethod
    async def update_suggestion(self, suggestion: ProjectSuggestion) -> ProjectSuggestion:
        """Persist mutable suggestion fields."""
