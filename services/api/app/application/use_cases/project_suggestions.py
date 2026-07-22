"""Use cases for project-aware suggestions on the chat empty state."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.application.use_cases.project_suggestion_sanitization import (
    safe_metadata,
    sanitize_suggestion_text,
)
from app.domain.entities import User
from app.domain.project_suggestions import (
    ProjectSuggestion,
    ProjectSuggestionProfile,
    SuggestionCalibrationRun,
    SuggestionCategory,
    SuggestionFreshnessState,
    SuggestionSource,
    SuggestionStatus,
)
from app.ports.project_suggestions import ProjectSuggestionRepository
from app.ports.repositories import RepositoryRepository
from app.ports.user_access import UserRepositoryAccessRepository


class ProjectSuggestionNotFoundError(LookupError):
    pass


class ProjectSuggestionAccessDeniedError(PermissionError):
    pass


@dataclass
class ProjectSuggestionCard:
    id: uuid.UUID
    title: str
    prompt: str
    category: str
    source: str
    freshness_state: str


@dataclass
class ProjectSuggestionsResult:
    repo_slug: str
    repo_name: str
    state: str
    last_calibrated_at: datetime | None
    cards: list[ProjectSuggestionCard]
    diagnostic: dict[str, str | bool]


@dataclass
class ProjectSuggestionStatusResult:
    repository_id: uuid.UUID
    counts: dict[str, int]
    last_run: SuggestionCalibrationRun | None


def _is_admin(user: User) -> bool:
    return user.is_admin or user.is_super_admin


async def _ensure_access(
    repository_id: uuid.UUID,
    current_user: User,
    access: UserRepositoryAccessRepository,
) -> None:
    if _is_admin(current_user):
        return
    if not await access.has_access(current_user.id, repository_id):
        raise ProjectSuggestionNotFoundError("Projeto nao encontrado.")


def _card(suggestion: ProjectSuggestion) -> ProjectSuggestionCard:
    return ProjectSuggestionCard(
        id=suggestion.id,
        title=suggestion.title,
        prompt=suggestion.prompt,
        category=suggestion.category.value,
        source=suggestion.source.value,
        freshness_state=suggestion.freshness_state.value,
    )


def build_initial_suggestions(profile: ProjectSuggestionProfile) -> list[ProjectSuggestion]:
    now = datetime.now(UTC)
    subject = profile.repo_name or profile.repo_slug
    doc_hint = profile.documents[0] if profile.documents else "documentos e skills cadastrados"
    skill_hint = profile.skills[0] if profile.skills else "as regras do projeto"
    specs = [
        (
            "Explore e entenda o codigo",
            f"Analise {subject} e explique a arquitetura, os fluxos principais e onde começar.",
            SuggestionCategory.EXPLORE,
        ),
        (
            "Crie algo util no projeto",
            f"Com base em {skill_hint}, sugira uma melhoria pequena e implemente em {subject}.",
            SuggestionCategory.BUILD,
        ),
        (
            "Revise riscos importantes",
            f"Revise {subject} procurando riscos, testes faltando e pontos de manutencao.",
            SuggestionCategory.REVIEW,
        ),
        (
            "Investigue problemas provaveis",
            f"Use {doc_hint} para levantar problemas comuns em {subject} e como validar.",
            SuggestionCategory.FIX,
        ),
    ]
    suggestions: list[ProjectSuggestion] = []
    for index, (title, prompt, category) in enumerate(specs):
        suggestions.append(
            ProjectSuggestion(
                id=uuid.uuid4(),
                repository_id=profile.repository_id,
                title=sanitize_suggestion_text(title, limit=64),
                prompt=sanitize_suggestion_text(prompt, limit=220),
                category=category,
                source=SuggestionSource.INITIAL_CONTEXT,
                priority=index,
                last_calibrated_at=now,
                metadata=safe_metadata(
                    {
                        "repo_slug": profile.repo_slug,
                        "documents_count": len(profile.documents),
                        "skills_count": len(profile.skills),
                    }
                ),
            )
        )
    return suggestions


class ListProjectSuggestions:
    def __init__(
        self,
        repos: RepositoryRepository,
        suggestions: ProjectSuggestionRepository,
        access: UserRepositoryAccessRepository,
    ) -> None:
        self._repos = repos
        self._suggestions = suggestions
        self._access = access

    async def execute(
        self,
        *,
        current_user: User,
        repo_slug: str,
        limit: int = 4,
    ) -> ProjectSuggestionsResult:
        repo = await self._repos.get_by_slug(repo_slug)
        if repo is None or not repo.active:
            raise ProjectSuggestionNotFoundError("Projeto nao encontrado.")
        await _ensure_access(repo.id, current_user, self._access)
        limit = max(3, min(4, limit))
        active = await self._suggestions.list_active(repo.id, limit)
        state = self._state(active)
        if len(active) < 3:
            profile = await self._suggestions.get_profile(repo.id)
            if profile is None:
                return self._empty(repo.slug, repo.name)
            generated = build_initial_suggestions(profile)
            active = await self._suggestions.save_suggestions(
                repo.id,
                generated,
                replace_source=SuggestionSource.INITIAL_CONTEXT.value,
            )
            state = "initial" if generated else "empty"
        last_run = await self._suggestions.latest_run(repo.id)
        return ProjectSuggestionsResult(
            repo_slug=repo.slug,
            repo_name=repo.name,
            state=state,
            last_calibrated_at=last_run.finished_at if last_run else None,
            cards=[_card(item) for item in active[:limit]],
            diagnostic={
                "using_initial_context": state in {"initial", "fallback"},
                "reason": "project_context"
                if state in {"initial", "fallback"}
                else "question_history",
            },
        )

    @staticmethod
    def _state(active: list[ProjectSuggestion]) -> str:
        if not active:
            return "empty"
        if any(item.source is SuggestionSource.QUESTION_HISTORY for item in active):
            return "calibrated"
        if any(item.source is SuggestionSource.INITIAL_CONTEXT for item in active):
            return "initial"
        return "fallback"

    @staticmethod
    def _empty(repo_slug: str, repo_name: str) -> ProjectSuggestionsResult:
        return ProjectSuggestionsResult(
            repo_slug=repo_slug,
            repo_name=repo_name,
            state="empty",
            last_calibrated_at=None,
            cards=[],
            diagnostic={"using_initial_context": False, "reason": "no_project_context"},
        )


class GetProjectSuggestionStatus:
    def __init__(self, suggestions: ProjectSuggestionRepository) -> None:
        self._suggestions = suggestions

    async def execute(self, *, repository_id: uuid.UUID) -> ProjectSuggestionStatusResult:
        counts = await self._suggestions.status_counts(repository_id)
        return ProjectSuggestionStatusResult(
            repository_id=repository_id,
            counts={status.value: value for status, value in counts.items()},
            last_run=await self._suggestions.latest_run(repository_id),
        )


class UpdateProjectSuggestionStatus:
    def __init__(self, suggestions: ProjectSuggestionRepository) -> None:
        self._suggestions = suggestions

    async def execute(
        self,
        *,
        suggestion_id: uuid.UUID,
        status: SuggestionStatus,
        current_user: User,
        reason: str | None,
    ) -> ProjectSuggestion:
        suggestion = await self._suggestions.get_suggestion(suggestion_id)
        if suggestion is None:
            raise ProjectSuggestionNotFoundError("Sugestao nao encontrada.")
        suggestion.status = status
        if status is SuggestionStatus.SUPPRESSED:
            suggestion.suppressed_at = datetime.now(UTC)
            suggestion.suppressed_by = current_user.id
            suggestion.suppression_reason = sanitize_suggestion_text(reason or "", limit=200)
        else:
            suggestion.suppressed_at = None
            suggestion.suppressed_by = None
            suggestion.suppression_reason = None
            suggestion.freshness_state = SuggestionFreshnessState.FRESH
        return await self._suggestions.update_suggestion(suggestion)
