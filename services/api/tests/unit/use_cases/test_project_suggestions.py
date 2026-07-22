from __future__ import annotations

import uuid

import pytest
from app.adapters.primary.http._project_suggestion_events import (
    schedule_project_suggestion_refresh,
)
from app.application.use_cases.project_suggestion_recalibration import (
    RunProjectSuggestionRecalibration,
    ScheduleProjectSuggestionRecalibration,
)
from app.application.use_cases.project_suggestion_sanitization import sanitize_suggestion_text
from app.application.use_cases.project_suggestions import (
    GetProjectSuggestionStatus,
    ListProjectSuggestions,
    ProjectSuggestionNotFoundError,
    UpdateProjectSuggestionStatus,
)
from app.domain.entities import Repository, User, UserRole
from app.domain.project_suggestions import (
    CalibrationStatus,
    CalibrationTrigger,
    ProjectQuestionSignal,
    ProjectSuggestion,
    ProjectSuggestionProfile,
    SuggestionCalibrationRun,
    SuggestionCategory,
    SuggestionSource,
    SuggestionStatus,
)
from app.infrastructure.project_suggestion_scheduler import register_project_suggestion_jobs


class FakeRepositoryRepo:
    def __init__(self, repo: Repository | None) -> None:
        self.repo = repo

    async def get_by_slug(self, slug: str) -> Repository | None:
        if self.repo and self.repo.slug == slug:
            return self.repo
        return None


class FakeAccessRepo:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed

    async def has_access(self, user_id: uuid.UUID, resource_id: uuid.UUID) -> bool:
        return self.allowed


class FakeSuggestionRepo:
    def __init__(
        self,
        profile: ProjectSuggestionProfile | None,
        *,
        active: list[ProjectSuggestion] | None = None,
        signals: list[ProjectQuestionSignal] | None = None,
        messages: int = 0,
        users: int = 0,
    ) -> None:
        self.profile = profile
        self.active = active or []
        self.signals = signals or []
        self.messages = messages
        self.users = users
        self.saved: list[ProjectSuggestion] = []
        self.finished: SuggestionCalibrationRun | None = None
        self.suggestion = active[0] if active else None

    async def list_active(self, repository_id: uuid.UUID, limit: int):
        return self.active[:limit]

    async def save_suggestions(self, repository_id: uuid.UUID, suggestions, *, replace_source=None):
        self.saved = suggestions
        return suggestions

    async def get_profile(self, repository_id: uuid.UUID):
        return self.profile

    async def latest_run(self, repository_id: uuid.UUID):
        return None

    async def list_question_signals(self, repository_id: uuid.UUID, repo_slug: str):
        return self.signals, self.messages, self.users

    async def create_run(self, repository_id: uuid.UUID, trigger: CalibrationTrigger):
        return SuggestionCalibrationRun(
            id=uuid.uuid4(), repository_id=repository_id, trigger=trigger
        )

    async def finish_run(self, run: SuggestionCalibrationRun):
        self.finished = run
        return run

    async def status_counts(self, repository_id: uuid.UUID):
        return {SuggestionStatus.ACTIVE: len(self.active)}

    async def get_suggestion(self, suggestion_id: uuid.UUID):
        if self.suggestion and self.suggestion.id == suggestion_id:
            return self.suggestion
        return None

    async def update_suggestion(self, suggestion: ProjectSuggestion):
        self.suggestion = suggestion
        return suggestion


@pytest.mark.asyncio
async def test_initial_suggestions_are_project_specific() -> None:
    repo_id = uuid.uuid4()
    repo = Repository(id=repo_id, slug="billing", name="Billing", clone_url="https://example")
    profile = ProjectSuggestionProfile(
        repository_id=repo_id,
        repo_slug="billing",
        repo_name="Billing",
        default_branch="main",
        documents=["Manual de faturamento"],
        skills=["Regra fiscal"],
    )
    uc = ListProjectSuggestions(
        FakeRepositoryRepo(repo), FakeSuggestionRepo(profile), FakeAccessRepo(True)
    )
    user = User(id=uuid.uuid4(), email="u@example.com", hashed_password="x")

    result = await uc.execute(current_user=user, repo_slug="billing")

    assert result.state == "initial"
    assert len(result.cards) == 4
    assert all("Billing" in card.prompt or "Regra fiscal" in card.prompt for card in result.cards)


@pytest.mark.asyncio
async def test_user_without_repository_access_is_hidden() -> None:
    repo_id = uuid.uuid4()
    repo = Repository(id=repo_id, slug="billing", name="Billing", clone_url="https://example")
    profile = ProjectSuggestionProfile(repo_id, "billing", "Billing", "main")
    uc = ListProjectSuggestions(
        FakeRepositoryRepo(repo), FakeSuggestionRepo(profile), FakeAccessRepo(False)
    )
    user = User(id=uuid.uuid4(), email="u@example.com", hashed_password="x", role=UserRole.USER)

    with pytest.raises(ProjectSuggestionNotFoundError):
        await uc.execute(current_user=user, repo_slug="billing")


def test_sanitizer_redacts_tokens_and_urls() -> None:
    text = sanitize_suggestion_text("Veja sk-1234567890abcdefghijklmnop em https://example.com")

    assert "sk-" not in text
    assert "https://" not in text
    assert "[redigido]" in text


@pytest.mark.asyncio
async def test_recalibration_saves_history_suggestions() -> None:
    repo_id = uuid.uuid4()
    profile = ProjectSuggestionProfile(repo_id, "billing", "Billing", "main")
    signal = ProjectQuestionSignal(
        category=SuggestionCategory.FIX,
        count=7,
        sample_prompt="Como corrigir falhas recorrentes no checkout?",
    )
    suggestions = FakeSuggestionRepo(profile, signals=[signal], messages=12, users=3)
    uc = RunProjectSuggestionRecalibration(suggestions)

    run = await uc.execute(repository_id=repo_id, trigger=CalibrationTrigger.DAILY)

    assert run.status is CalibrationStatus.SUCCEEDED
    assert run.eligible_message_count == 12
    assert run.eligible_user_count == 3
    assert run.suggestions_created == 1
    assert suggestions.saved[0].source is SuggestionSource.QUESTION_HISTORY
    assert suggestions.saved[0].metadata["question_count"] == 7


@pytest.mark.asyncio
async def test_recalibration_skips_when_history_has_no_signals() -> None:
    repo_id = uuid.uuid4()
    suggestions = FakeSuggestionRepo(
        ProjectSuggestionProfile(repo_id, "billing", "Billing", "main")
    )
    uc = ScheduleProjectSuggestionRecalibration(RunProjectSuggestionRecalibration(suggestions))

    run = await uc.execute(repository_id=repo_id, trigger=CalibrationTrigger.MANUAL, force=True)

    assert run.status is CalibrationStatus.SKIPPED
    assert run.finished_at is not None
    assert suggestions.saved == []


@pytest.mark.asyncio
async def test_recalibration_fails_when_project_profile_is_missing() -> None:
    repo_id = uuid.uuid4()
    uc = RunProjectSuggestionRecalibration(FakeSuggestionRepo(None))

    run = await uc.execute(repository_id=repo_id, trigger=CalibrationTrigger.MANUAL)

    assert run.status is CalibrationStatus.FAILED
    assert run.failure_reason == "Projeto nao encontrado."


@pytest.mark.asyncio
async def test_admin_can_suppress_and_reactivate_suggestion() -> None:
    repo_id = uuid.uuid4()
    admin = User(
        id=uuid.uuid4(), email="admin@example.com", hashed_password="x", role=UserRole.ADMIN
    )
    suggestion = ProjectSuggestion(
        id=uuid.uuid4(),
        repository_id=repo_id,
        title="Revisar",
        prompt="Revise o projeto",
        category=SuggestionCategory.REVIEW,
        source=SuggestionSource.INITIAL_CONTEXT,
    )
    suggestions = FakeSuggestionRepo(
        ProjectSuggestionProfile(repo_id, "billing", "Billing", "main"), active=[suggestion]
    )
    uc = UpdateProjectSuggestionStatus(suggestions)

    suppressed = await uc.execute(
        suggestion_id=suggestion.id,
        status=SuggestionStatus.SUPPRESSED,
        current_user=admin,
        reason="nao usar https://example.com",
    )
    assert suppressed.suppressed_by == admin.id
    assert "[link]" in (suppressed.suppression_reason or "")

    reactivated = await uc.execute(
        suggestion_id=suggestion.id,
        status=SuggestionStatus.ACTIVE,
        current_user=admin,
        reason=None,
    )

    assert reactivated.suppressed_by is None
    assert reactivated.suppression_reason is None


@pytest.mark.asyncio
async def test_status_counts_are_returned_with_string_keys() -> None:
    repo_id = uuid.uuid4()
    suggestion = ProjectSuggestion(
        id=uuid.uuid4(),
        repository_id=repo_id,
        title="Explorar",
        prompt="Explique a arquitetura",
        category=SuggestionCategory.EXPLORE,
        source=SuggestionSource.INITIAL_CONTEXT,
    )
    uc = GetProjectSuggestionStatus(
        FakeSuggestionRepo(
            ProjectSuggestionProfile(repo_id, "billing", "Billing", "main"),
            active=[suggestion],
        )
    )

    result = await uc.execute(repository_id=repo_id)

    assert result.counts == {"active": 1}


@pytest.mark.asyncio
async def test_event_bridge_ignores_missing_repository_id() -> None:
    await schedule_project_suggestion_refresh(None, None, CalibrationTrigger.SKILL_CHANGED)


def test_register_project_suggestion_jobs_adds_daily_recalibration() -> None:
    class FakeScheduler:
        def __init__(self) -> None:
            self.calls = []

        def add_job(self, func, trigger, **kwargs) -> None:
            self.calls.append((func, trigger, kwargs))

    scheduler = FakeScheduler()

    register_project_suggestion_jobs(scheduler, object())

    func, trigger, kwargs = scheduler.calls[0]
    assert func.__name__ == "_run_daily_recalibration"
    assert trigger == "cron"
    assert kwargs["hour"] == 3
    assert kwargs["minute"] == 20
    assert kwargs["id"] == "project_suggestions_daily"
