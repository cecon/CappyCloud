"""Dependency wiring for project suggestion use cases."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.secondary.persistence.sqlalchemy_project_suggestion_repo import (
    SQLAlchemyProjectSuggestionRepository,
)
from app.application.use_cases.project_suggestion_recalibration import (
    RunProjectSuggestionRecalibration,
    ScheduleProjectSuggestionRecalibration,
)
from app.application.use_cases.project_suggestions import (
    GetProjectSuggestionStatus,
    ListProjectSuggestions,
    UpdateProjectSuggestionStatus,
)
from app.ports.project_suggestions import ProjectSuggestionRepository
from app.ports.repositories import RepositoryRepository
from app.ports.user_access import UserRepositoryAccessRepository

from .deps import get_db_session, get_repository_repo, get_user_repository_access_repo


def get_project_suggestion_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProjectSuggestionRepository:
    return SQLAlchemyProjectSuggestionRepository(session)


def get_user_project_suggestions_uc(
    repos: Annotated[RepositoryRepository, Depends(get_repository_repo)],
    suggestions: Annotated[ProjectSuggestionRepository, Depends(get_project_suggestion_repo)],
    access: Annotated[UserRepositoryAccessRepository, Depends(get_user_repository_access_repo)],
) -> ListProjectSuggestions:
    return ListProjectSuggestions(repos, suggestions, access)


def get_run_project_suggestion_recalibration_uc(
    suggestions: Annotated[ProjectSuggestionRepository, Depends(get_project_suggestion_repo)],
) -> RunProjectSuggestionRecalibration:
    return RunProjectSuggestionRecalibration(suggestions)


def get_schedule_project_suggestion_recalibration_uc(
    recalibrate: Annotated[
        RunProjectSuggestionRecalibration,
        Depends(get_run_project_suggestion_recalibration_uc),
    ],
) -> ScheduleProjectSuggestionRecalibration:
    return ScheduleProjectSuggestionRecalibration(recalibrate)


def get_project_suggestion_status_uc(
    suggestions: Annotated[ProjectSuggestionRepository, Depends(get_project_suggestion_repo)],
) -> GetProjectSuggestionStatus:
    return GetProjectSuggestionStatus(suggestions)


def get_update_project_suggestion_status_uc(
    suggestions: Annotated[ProjectSuggestionRepository, Depends(get_project_suggestion_repo)],
) -> UpdateProjectSuggestionStatus:
    return UpdateProjectSuggestionStatus(suggestions)
