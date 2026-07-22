"""HTTP-side event bridge for project suggestion recalibration."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.secondary.persistence.sqlalchemy_project_suggestion_repo import (
    SQLAlchemyProjectSuggestionRepository,
)
from app.application.use_cases.project_suggestion_recalibration import (
    RunProjectSuggestionRecalibration,
    ScheduleProjectSuggestionRecalibration,
)
from app.domain.project_suggestions import CalibrationTrigger

log = logging.getLogger(__name__)


async def schedule_project_suggestion_refresh(
    session: AsyncSession,
    repository_id: uuid.UUID | None,
    trigger: CalibrationTrigger,
) -> None:
    if repository_id is None:
        return
    try:
        repo = SQLAlchemyProjectSuggestionRepository(session)
        uc = ScheduleProjectSuggestionRecalibration(RunProjectSuggestionRecalibration(repo))
        await uc.execute(repository_id=repository_id, trigger=trigger)
    except Exception:
        log.exception("Falha ao agendar recalibracao de sugestoes para %s", repository_id)
