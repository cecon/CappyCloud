"""APScheduler integration for project suggestion recalibration."""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.adapters.secondary.persistence.sqlalchemy_project_suggestion_repo import (
    SQLAlchemyProjectSuggestionRepository,
)
from app.application.use_cases.project_suggestion_recalibration import (
    RunProjectSuggestionRecalibration,
)
from app.domain.project_suggestions import CalibrationTrigger
from app.infrastructure.orm_models import Repository

log = logging.getLogger(__name__)


def register_project_suggestion_jobs(
    scheduler: AsyncIOScheduler,
    session_factory: async_sessionmaker,
) -> None:
    scheduler.add_job(
        _run_daily_recalibration,
        "cron",
        hour=3,
        minute=20,
        id="project_suggestions_daily",
        replace_existing=True,
        kwargs={"session_factory": session_factory},
    )


async def _run_daily_recalibration(session_factory: async_sessionmaker) -> None:
    async with session_factory() as session:
        repo_ids = (
            await session.scalars(select(Repository.id).where(Repository.active.is_(True)))
        ).all()
    for repository_id in repo_ids:
        try:
            async with session_factory() as session:
                repo = SQLAlchemyProjectSuggestionRepository(session)
                uc = RunProjectSuggestionRecalibration(repo)
                await uc.execute(repository_id=repository_id, trigger=CalibrationTrigger.DAILY)
        except Exception:
            log.exception("Falha ao recalibrar sugestoes do projeto %s", repository_id)
