"""Use cases that recalibrate project suggestions from anonymized chat history."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.application.use_cases.project_suggestion_sanitization import (
    safe_metadata,
    sanitize_suggestion_text,
)
from app.domain.project_suggestions import (
    CalibrationStatus,
    CalibrationTrigger,
    ProjectQuestionSignal,
    ProjectSuggestion,
    ProjectSuggestionProfile,
    SuggestionCalibrationRun,
    SuggestionCategory,
    SuggestionSource,
)
from app.ports.project_suggestions import ProjectSuggestionRepository


def build_history_suggestions(
    profile: ProjectSuggestionProfile,
    signals: list[ProjectQuestionSignal],
) -> list[ProjectSuggestion]:
    now = datetime.now(UTC)
    suggestions: list[ProjectSuggestion] = []
    for index, signal in enumerate(signals[:4]):
        prompt = (
            signal.sample_prompt or f"Quais perguntas recorrentes aparecem em {profile.repo_name}?"
        )
        suggestions.append(
            ProjectSuggestion(
                id=uuid.uuid4(),
                repository_id=profile.repository_id,
                title=_title_for_signal(signal),
                prompt=sanitize_suggestion_text(prompt, limit=220),
                category=signal.category,
                source=SuggestionSource.QUESTION_HISTORY,
                priority=index,
                last_calibrated_at=now,
                metadata=safe_metadata({"question_count": signal.count}),
            )
        )
    return suggestions


def _title_for_signal(signal: ProjectQuestionSignal) -> str:
    labels = {
        SuggestionCategory.FIX: "Corrigir problemas frequentes",
        SuggestionCategory.REVIEW: "Revisar o que mais pedem",
        SuggestionCategory.BUILD: "Criar a melhoria mais pedida",
        SuggestionCategory.SUPPORT: "Ajudar no suporte recorrente",
        SuggestionCategory.EXPLORE: "Entender fluxos recorrentes",
    }
    return labels.get(signal.category, "Pergunta recorrente")


class RunProjectSuggestionRecalibration:
    def __init__(self, suggestions: ProjectSuggestionRepository) -> None:
        self._suggestions = suggestions

    async def execute(
        self,
        *,
        repository_id: uuid.UUID,
        trigger: CalibrationTrigger,
    ) -> SuggestionCalibrationRun:
        profile = await self._suggestions.get_profile(repository_id)
        if profile is None:
            return SuggestionCalibrationRun(
                id=uuid.uuid4(),
                repository_id=repository_id,
                trigger=trigger,
                status=CalibrationStatus.FAILED,
                failure_reason="Projeto nao encontrado.",
            )
        run = await self._suggestions.create_run(repository_id, trigger)
        signals, messages, users = await self._suggestions.list_question_signals(
            repository_id,
            profile.repo_slug,
        )
        run.eligible_message_count = messages
        run.eligible_user_count = users
        if not signals:
            run.status = CalibrationStatus.SKIPPED
            return await self._finish(run)
        saved = await self._suggestions.save_suggestions(
            repository_id,
            build_history_suggestions(profile, signals),
            replace_source=SuggestionSource.QUESTION_HISTORY.value,
        )
        run.suggestions_created = len(saved)
        run.suggestions_activated = len(saved)
        run.status = CalibrationStatus.SUCCEEDED
        return await self._finish(run)

    async def _finish(self, run: SuggestionCalibrationRun) -> SuggestionCalibrationRun:
        now = datetime.now(UTC)
        run.started_at = run.started_at or now
        run.finished_at = now
        return await self._suggestions.finish_run(run)


class ScheduleProjectSuggestionRecalibration:
    def __init__(self, recalibrate: RunProjectSuggestionRecalibration) -> None:
        self._recalibrate = recalibrate

    async def execute(
        self,
        *,
        repository_id: uuid.UUID,
        trigger: CalibrationTrigger,
        force: bool = False,
    ) -> SuggestionCalibrationRun:
        return await self._recalibrate.execute(repository_id=repository_id, trigger=trigger)
