"""SQLAlchemy adapter for project-aware chat suggestions."""

from __future__ import annotations

import re
import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.secondary.persistence.project_suggestion_mappers import (
    run_to_entity,
    suggestion_to_entity,
    suggestion_to_orm,
)
from app.application.use_cases.project_suggestion_sanitization import sanitize_suggestion_text
from app.domain.project_suggestions import (
    CalibrationStatus,
    CalibrationTrigger,
    ProjectQuestionSignal,
    ProjectSuggestion,
    ProjectSuggestionProfile,
    SuggestionCalibrationRun,
    SuggestionCategory,
    SuggestionSafetyState,
    SuggestionStatus,
)
from app.infrastructure.orm_models import Conversation, Document, Message, Repository, Skill
from app.infrastructure.orm_models_access import UserRepositoryAccess
from app.infrastructure.orm_models_project_suggestions import (
    ProjectSuggestion as ProjectSuggestionORM,
)
from app.infrastructure.orm_models_project_suggestions import (
    ProjectSuggestionCalibrationRun as CalibrationRunORM,
)
from app.ports.project_suggestions import ProjectSuggestionRepository


class SQLAlchemyProjectSuggestionRepository(ProjectSuggestionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active(self, repository_id: uuid.UUID, limit: int) -> list[ProjectSuggestion]:
        rows = await self._session.execute(
            select(ProjectSuggestionORM)
            .where(
                ProjectSuggestionORM.repository_id == repository_id,
                ProjectSuggestionORM.status == SuggestionStatus.ACTIVE.value,
                ProjectSuggestionORM.safety_state == SuggestionSafetyState.SAFE.value,
            )
            .order_by(ProjectSuggestionORM.priority.asc(), ProjectSuggestionORM.updated_at.desc())
            .limit(limit)
        )
        return [suggestion_to_entity(row) for row in rows.scalars().all()]

    async def save_suggestions(
        self,
        repository_id: uuid.UUID,
        suggestions: list[ProjectSuggestion],
        *,
        replace_source: str | None = None,
    ) -> list[ProjectSuggestion]:
        if replace_source:
            await self._session.execute(
                update(ProjectSuggestionORM)
                .where(
                    ProjectSuggestionORM.repository_id == repository_id,
                    ProjectSuggestionORM.source == replace_source,
                    ProjectSuggestionORM.status == SuggestionStatus.ACTIVE.value,
                )
                .values(status=SuggestionStatus.STALE.value, freshness_state="stale")
            )
        rows: list[ProjectSuggestionORM] = []
        for suggestion in suggestions:
            row = suggestion_to_orm(suggestion)
            self._session.add(row)
            rows.append(row)
        await self._session.commit()
        for row in rows:
            await self._session.refresh(row)
        return [suggestion_to_entity(row) for row in rows]

    async def get_profile(self, repository_id: uuid.UUID) -> ProjectSuggestionProfile | None:
        repo = await self._session.get(Repository, repository_id)
        if not repo or not repo.active:
            return None
        documents = await self._session.scalars(
            select(Document.title)
            .where(Document.repository_id == repository_id, Document.status == "indexed")
            .order_by(Document.updated_at.desc())
            .limit(6)
        )
        skills = await self._session.scalars(
            select(Skill.title)
            .where(Skill.repository_id == repository_id, Skill.active.is_(True))
            .order_by(Skill.updated_at.desc())
            .limit(6)
        )
        return ProjectSuggestionProfile(
            repository_id=repo.id,
            repo_slug=repo.slug,
            repo_name=repo.name,
            default_branch=repo.default_branch,
            documents=list(documents.all()),
            skills=list(skills.all()),
        )

    async def list_question_signals(
        self,
        repository_id: uuid.UUID,
        repo_slug: str,
    ) -> tuple[list[ProjectQuestionSignal], int, int]:
        since = datetime.now(UTC) - timedelta(days=90)
        allowed_users = set(
            (
                await self._session.scalars(
                    select(UserRepositoryAccess.user_id).where(
                        UserRepositoryAccess.repository_id == repository_id
                    )
                )
            ).all()
        )
        rows = await self._session.execute(
            select(Message.content, Conversation.user_id, Conversation.repos)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(Message.role == "user", Message.created_at >= since)
            .order_by(Message.created_at.desc())
            .limit(600)
        )
        buckets: Counter[SuggestionCategory] = Counter()
        samples: dict[SuggestionCategory, str] = {}
        users: set[uuid.UUID] = set()
        total = 0
        for content, user_id, repos in rows.all():
            if user_id not in allowed_users:
                continue
            if not _conversation_mentions_repo(repos, repo_slug):
                continue
            category = _classify(content)
            buckets[category] += 1
            samples.setdefault(category, sanitize_suggestion_text(content, limit=180))
            users.add(user_id)
            total += 1
        signals = [
            ProjectQuestionSignal(category=category, count=count, sample_prompt=samples[category])
            for category, count in buckets.most_common(4)
        ]
        return signals, total, len(users)

    async def create_run(
        self,
        repository_id: uuid.UUID,
        trigger: CalibrationTrigger,
    ) -> SuggestionCalibrationRun:
        row = CalibrationRunORM(
            id=uuid.uuid4(),
            repository_id=repository_id,
            trigger=trigger.value,
            status=CalibrationStatus.RUNNING.value,
            started_at=datetime.now(UTC),
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return run_to_entity(row)

    async def finish_run(self, run: SuggestionCalibrationRun) -> SuggestionCalibrationRun:
        row = await self._session.get(CalibrationRunORM, run.id)
        if row is None:
            return run
        row.status = run.status.value
        row.started_at = run.started_at
        row.finished_at = run.finished_at
        row.eligible_message_count = run.eligible_message_count
        row.eligible_user_count = run.eligible_user_count
        row.suggestions_created = run.suggestions_created
        row.suggestions_activated = run.suggestions_activated
        row.suggestions_suppressed = run.suggestions_suppressed
        row.failure_reason = run.failure_reason
        await self._session.commit()
        await self._session.refresh(row)
        return run_to_entity(row)

    async def latest_run(self, repository_id: uuid.UUID) -> SuggestionCalibrationRun | None:
        row = await self._session.scalar(
            select(CalibrationRunORM)
            .where(CalibrationRunORM.repository_id == repository_id)
            .order_by(CalibrationRunORM.created_at.desc())
            .limit(1)
        )
        return run_to_entity(row) if row else None

    async def status_counts(self, repository_id: uuid.UUID) -> dict[SuggestionStatus, int]:
        rows = await self._session.execute(
            select(ProjectSuggestionORM.status, func.count(ProjectSuggestionORM.id))
            .where(ProjectSuggestionORM.repository_id == repository_id)
            .group_by(ProjectSuggestionORM.status)
        )
        counts: defaultdict[SuggestionStatus, int] = defaultdict(int)
        for status, count in rows.all():
            counts[SuggestionStatus(status)] = int(count)
        return dict(counts)

    async def get_suggestion(self, suggestion_id: uuid.UUID) -> ProjectSuggestion | None:
        row = await self._session.get(ProjectSuggestionORM, suggestion_id)
        return suggestion_to_entity(row) if row else None

    async def update_suggestion(self, suggestion: ProjectSuggestion) -> ProjectSuggestion:
        row = await self._session.get(ProjectSuggestionORM, suggestion.id)
        if row is None:
            return suggestion
        row.status = suggestion.status.value
        row.freshness_state = suggestion.freshness_state.value
        row.suppressed_at = suggestion.suppressed_at
        row.suppressed_by = suggestion.suppressed_by
        row.suppression_reason = suggestion.suppression_reason
        await self._session.commit()
        await self._session.refresh(row)
        return suggestion_to_entity(row)


def _conversation_mentions_repo(repos: list[dict] | None, repo_slug: str) -> bool:
    return any(
        str(item.get("slug") or item.get("repo_slug") or "") == repo_slug for item in repos or []
    )


def _classify(content: str) -> SuggestionCategory:
    text = (content or "").lower()
    if re.search(r"\b(erro|bug|falha|problema|quebrou|corrigir|consertar)\b", text):
        return SuggestionCategory.FIX
    if re.search(r"\b(revis|risco|teste|seguran|performance|melhorar)\b", text):
        return SuggestionCategory.REVIEW
    if re.search(r"\b(crie|criar|implemente|adicionar|novo|feature|recurso)\b", text):
        return SuggestionCategory.BUILD
    if re.search(r"\b(cliente|suporte|atendimento|chamado)\b", text):
        return SuggestionCategory.SUPPORT
    return SuggestionCategory.EXPLORE
