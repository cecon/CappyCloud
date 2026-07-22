"""Mapping helpers for project suggestion ORM rows."""

from __future__ import annotations

from app.domain.project_suggestions import (
    CalibrationStatus,
    CalibrationTrigger,
    ProjectSuggestion,
    SuggestionCalibrationRun,
    SuggestionCategory,
    SuggestionFreshnessState,
    SuggestionSafetyState,
    SuggestionSource,
    SuggestionStatus,
)
from app.infrastructure.orm_models_project_suggestions import (
    ProjectSuggestion as ProjectSuggestionORM,
)
from app.infrastructure.orm_models_project_suggestions import (
    ProjectSuggestionCalibrationRun as CalibrationRunORM,
)


def suggestion_to_entity(row: ProjectSuggestionORM) -> ProjectSuggestion:
    return ProjectSuggestion(
        id=row.id,
        repository_id=row.repository_id,
        title=row.title,
        prompt=row.prompt,
        category=SuggestionCategory(row.category),
        source=SuggestionSource(row.source),
        status=SuggestionStatus(row.status),
        priority=row.priority,
        safety_state=SuggestionSafetyState(row.safety_state),
        freshness_state=SuggestionFreshnessState(row.freshness_state),
        analysis_window_start=row.analysis_window_start,
        analysis_window_end=row.analysis_window_end,
        last_calibrated_at=row.last_calibrated_at,
        suppressed_at=row.suppressed_at,
        suppressed_by=row.suppressed_by,
        suppression_reason=row.suppression_reason,
        metadata=dict(row.suggestion_metadata or {}),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def suggestion_to_orm(suggestion: ProjectSuggestion) -> ProjectSuggestionORM:
    return ProjectSuggestionORM(
        id=suggestion.id,
        repository_id=suggestion.repository_id,
        title=suggestion.title,
        prompt=suggestion.prompt,
        category=suggestion.category.value,
        source=suggestion.source.value,
        status=suggestion.status.value,
        priority=suggestion.priority,
        safety_state=suggestion.safety_state.value,
        freshness_state=suggestion.freshness_state.value,
        analysis_window_start=suggestion.analysis_window_start,
        analysis_window_end=suggestion.analysis_window_end,
        last_calibrated_at=suggestion.last_calibrated_at,
        suppressed_at=suggestion.suppressed_at,
        suppressed_by=suggestion.suppressed_by,
        suppression_reason=suggestion.suppression_reason,
        suggestion_metadata=suggestion.metadata,
    )


def run_to_entity(row: CalibrationRunORM) -> SuggestionCalibrationRun:
    return SuggestionCalibrationRun(
        id=row.id,
        repository_id=row.repository_id,
        trigger=CalibrationTrigger(row.trigger),
        status=CalibrationStatus(row.status),
        started_at=row.started_at,
        finished_at=row.finished_at,
        analysis_window_start=row.analysis_window_start,
        analysis_window_end=row.analysis_window_end,
        eligible_message_count=row.eligible_message_count,
        eligible_user_count=row.eligible_user_count,
        suggestions_created=row.suggestions_created,
        suggestions_activated=row.suggestions_activated,
        suggestions_suppressed=row.suggestions_suppressed,
        failure_reason=row.failure_reason,
        created_at=row.created_at,
    )
