"""HTTP adapter for project-aware chat suggestions."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.adapters.primary.http.deps import (
    get_authenticated_user,
    require_role,
)
from app.adapters.primary.http.deps_project_suggestions import (
    get_project_suggestion_status_uc,
    get_schedule_project_suggestion_recalibration_uc,
    get_update_project_suggestion_status_uc,
    get_user_project_suggestions_uc,
)
from app.application.use_cases.project_suggestion_recalibration import (
    ScheduleProjectSuggestionRecalibration,
)
from app.application.use_cases.project_suggestions import (
    GetProjectSuggestionStatus,
    ListProjectSuggestions,
    ProjectSuggestionNotFoundError,
    UpdateProjectSuggestionStatus,
)
from app.domain.entities import User, UserRole
from app.domain.project_suggestions import CalibrationTrigger, SuggestionStatus
from app.schemas_project_suggestions import (
    ProjectSuggestionPatchBody,
    ProjectSuggestionPatchOut,
    ProjectSuggestionRecalibrateBody,
    ProjectSuggestionRunOut,
    ProjectSuggestionsOut,
    ProjectSuggestionStatusOut,
)

router = APIRouter(prefix="/project-suggestions", tags=["project-suggestions"])


@router.get("", response_model=ProjectSuggestionsOut)
async def list_project_suggestions(
    repo_slug: Annotated[str, Query(min_length=1)],
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[ListProjectSuggestions, Depends(get_user_project_suggestions_uc)],
    limit: Annotated[int, Query(ge=3, le=4)] = 4,
) -> ProjectSuggestionsOut:
    try:
        result = await uc.execute(current_user=current, repo_slug=repo_slug, limit=limit)
    except ProjectSuggestionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ProjectSuggestionsOut.model_validate(result, from_attributes=True)


@router.post(
    "/{repository_id}/recalibrate",
    response_model=ProjectSuggestionRunOut,
    status_code=202,
)
async def recalibrate_project_suggestions(
    repository_id: uuid.UUID,
    body: ProjectSuggestionRecalibrateBody,
    _admin: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    uc: Annotated[
        ScheduleProjectSuggestionRecalibration,
        Depends(get_schedule_project_suggestion_recalibration_uc),
    ],
) -> ProjectSuggestionRunOut:
    run = await uc.execute(
        repository_id=repository_id,
        trigger=CalibrationTrigger(body.trigger),
        force=body.force,
    )
    return ProjectSuggestionRunOut.model_validate(run, from_attributes=True)


@router.patch("/{suggestion_id}", response_model=ProjectSuggestionPatchOut)
async def update_project_suggestion(
    suggestion_id: uuid.UUID,
    body: ProjectSuggestionPatchBody,
    admin: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    uc: Annotated[UpdateProjectSuggestionStatus, Depends(get_update_project_suggestion_status_uc)],
) -> ProjectSuggestionPatchOut:
    try:
        suggestion = await uc.execute(
            suggestion_id=suggestion_id,
            status=SuggestionStatus(body.status),
            current_user=admin,
            reason=body.reason,
        )
    except ProjectSuggestionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ProjectSuggestionPatchOut(
        id=suggestion.id,
        status=suggestion.status.value,
        suppressed_at=suggestion.suppressed_at,
    )


@router.get("/{repository_id}/status", response_model=ProjectSuggestionStatusOut)
async def project_suggestion_status(
    repository_id: uuid.UUID,
    _admin: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    uc: Annotated[GetProjectSuggestionStatus, Depends(get_project_suggestion_status_uc)],
) -> ProjectSuggestionStatusOut:
    result = await uc.execute(repository_id=repository_id)
    last_run = (
        ProjectSuggestionRunOut.model_validate(result.last_run, from_attributes=True)
        if result.last_run
        else None
    )
    return ProjectSuggestionStatusOut(
        repository_id=result.repository_id,
        counts=result.counts,
        last_run=last_run,
    )
