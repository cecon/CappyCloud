"""Relatório de uso: agregação, período, semanas ISO e escopo de acesso (fakes)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest
from app.application.use_cases._workspace_report_metrics import (
    REPORT_TZ,
    aggregate_report,
    iso_weeks,
    period_bounds,
)
from app.application.use_cases.workspace_report import (
    BuildWorkspaceReport,
    GetWorkspaceReportOptions,
    GetWorkspaceReportThemes,
    InvalidReportPeriodError,
    ReportViewer,
    UpdateWorkspaceReportThemes,
    WorkspaceReportAccessDeniedError,
    WorkspaceReportNotFoundError,
    resolve_period,
)
from app.domain.report_themes import InvalidThemeRulesError
from app.ports.workspace_report import (
    ReportConversation,
    ReportMessage,
    ReportWorkspace,
    branches_from_repos,
)

from tests.fakes_reports import InMemoryWorkspaceReportRepository

PROTEUS = ReportWorkspace(
    id=uuid.uuid4(), slug="proteus", name="PROTEUS", theme_preset="nfse-protheus"
)
SELLER = ReportWorkspace(id=uuid.uuid4(), slug="seller", name="SELLER")
SUPER = ReportViewer(user_id=uuid.uuid4(), is_super_admin=True)
NOW = datetime(2026, 10, 9, 15, 0, tzinfo=UTC)


def _local(*args: int) -> datetime:
    return datetime(*args, tzinfo=REPORT_TZ).astimezone(UTC)


def _conv(ws: ReportWorkspace, email: str, title: str, branches: set[str]) -> ReportConversation:
    return ReportConversation(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        user_email=email,
        title=title,
        branches=frozenset(branches),
    )


def _msg(conv: ReportConversation, when: datetime, cost: float) -> ReportMessage:
    return ReportMessage(conversation_id=conv.id, created_at=when, cost_usd=cost)


@pytest.fixture
def repo() -> InMemoryWorkspaceReportRepository:
    repo = InMemoryWorkspaceReportRepository()
    repo.add_workspace(PROTEUS)
    repo.add_workspace(SELLER)
    a = _conv(PROTEUS, "ana@linx.com", "Rejeição E370 retenções Jundiaí", {"main"})
    b = _conv(PROTEUS, "bruno@linx.com", "Falha de schema SP indDest", {"main"})
    c = _conv(PROTEUS, "ana@linx.com", "ola", {"release"})
    s = _conv(SELLER, "carla@linx.com", "como ativar o sap no seller", {"master"})
    repo.add_conversation(
        a, _msg(a, _local(2026, 9, 1, 10), 1.0), _msg(a, _local(2026, 9, 8, 9), 0.5)
    )
    repo.add_conversation(b, _msg(b, _local(2026, 9, 7, 23, 59), 2.0))
    # Só antes do período: não conta.
    repo.add_conversation(c, _msg(c, _local(2026, 8, 31, 23, 59), 9.0))
    repo.add_conversation(s, _msg(s, _local(2026, 9, 2, 8), 4.0))
    return repo


async def _build(
    repo: InMemoryWorkspaceReportRepository, viewer: ReportViewer = SUPER, **kw: object
):
    params: dict[str, object] = {
        "workspace_id": PROTEUS.id,
        "branch": None,
        "start": date(2026, 9, 1),
        "end": date(2026, 9, 8),
        "now": NOW,
    }
    params.update(kw)
    return await BuildWorkspaceReport(repo).execute(viewer, **params)  # type: ignore[arg-type]


async def test_report_counts_only_messages_inside_period(
    repo: InMemoryWorkspaceReportRepository,
) -> None:
    built = await _build(repo)
    totals = built.report.totals
    assert totals.consultations == 2
    assert totals.analysts == 2
    assert totals.messages == 3
    assert totals.cost_usd == 3.5
    assert totals.avg_cost_per_consultation == 1.75
    assert totals.avg_cost_per_analyst == 1.75
    assert built.scope_slug == "proteus"
    assert built.workspace_name == "PROTEUS"


async def test_period_end_is_inclusive_until_midnight_local(
    repo: InMemoryWorkspaceReportRepository,
) -> None:
    built = await _build(repo, start=date(2026, 9, 7), end=date(2026, 9, 7))
    assert [c.title for c in built.report.consultations] == ["Falha de schema SP indDest"]
    built = await _build(repo, start=date(2026, 8, 31), end=date(2026, 8, 31))
    assert [c.title for c in built.report.consultations] == ["ola"]


async def test_analysts_table_uses_email_and_part_before_at(
    repo: InMemoryWorkspaceReportRepository,
) -> None:
    analysts = (await _build(repo)).report.analysts
    assert [(a.email, a.label, a.consultations, a.cost_usd) for a in analysts] == [
        ("bruno@linx.com", "bruno", 1, 2.0),
        ("ana@linx.com", "ana", 1, 1.5),
    ]


async def test_weeks_cover_period_with_empty_weeks(repo: InMemoryWorkspaceReportRepository) -> None:
    weeks = (await _build(repo, end=date(2026, 9, 20))).report.weeks
    assert [(w.week, w.start, w.consultations, w.cost_usd) for w in weeks] == [
        ("2026-W36", date(2026, 8, 31), 1, 1.0),
        ("2026-W37", date(2026, 9, 7), 2, 2.5),
        ("2026-W38", date(2026, 9, 14), 0, 0.0),
    ]


async def test_themes_follow_workspace_preset(repo: InMemoryWorkspaceReportRepository) -> None:
    themes = (await _build(repo)).report.themes
    assert [(t.key, t.consultations, t.cost_usd) for t in themes] == [
        ("nfse-schema-xml", 1, 2.0),
        ("nfse-retencoes", 1, 1.5),
    ]


async def test_branch_filter_keeps_only_matching_conversations(
    repo: InMemoryWorkspaceReportRepository,
) -> None:
    built = await _build(repo, branch=" release ", start=date(2026, 8, 1))
    assert built.branch == "release"
    assert [c.title for c in built.report.consultations] == ["ola"]
    assert (await _build(repo, branch="nao-existe")).report.totals.consultations == 0


async def test_all_workspaces_for_super_admin_breaks_down_per_workspace(
    repo: InMemoryWorkspaceReportRepository,
) -> None:
    built = await _build(repo, workspace_id=None)
    assert built.scope_slug == "todos"
    assert built.workspace_name is None
    assert built.report.totals.consultations == 3
    assert [(w.slug, w.consultations, w.cost_usd) for w in built.report.workspaces] == [
        ("proteus", 2, 3.5),
        ("seller", 1, 4.0),
    ]
    # Cada workspace usa os próprios temas; "Outros" sempre por último.
    assert {t.key for t in built.report.themes} == {
        "nfse-schema-xml",
        "nfse-retencoes",
        "configuracao",
    }


async def test_regular_admin_only_sees_granted_workspaces(
    repo: InMemoryWorkspaceReportRepository,
) -> None:
    admin = ReportViewer(user_id=uuid.uuid4(), is_super_admin=False)
    repo.grant(admin.user_id, SELLER.id)
    built = await _build(repo, admin, workspace_id=None)
    assert [w.slug for w in built.report.workspaces] == ["seller"]
    assert built.report.totals.cost_usd == 4.0
    with pytest.raises(WorkspaceReportAccessDeniedError):
        await _build(repo, admin)
    with pytest.raises(WorkspaceReportNotFoundError):
        await _build(repo, admin, workspace_id=uuid.uuid4())
    nobody = ReportViewer(user_id=uuid.uuid4(), is_super_admin=False)
    assert (await _build(repo, nobody, workspace_id=None)).report.totals.consultations == 0


async def test_empty_period_has_zero_averages(repo: InMemoryWorkspaceReportRepository) -> None:
    totals = (await _build(repo, start=date(2025, 1, 1), end=date(2025, 1, 5))).report.totals
    assert (totals.consultations, totals.cost_usd, totals.avg_cost_per_consultation) == (
        0,
        0.0,
        0.0,
    )
    assert totals.avg_cost_per_analyst == 0.0


def test_resolve_period_defaults_and_limits() -> None:
    today = date(2026, 10, 9)
    assert resolve_period(None, None, today) == (date(2026, 9, 10), today)
    assert resolve_period(date(2026, 10, 9), date(2026, 10, 9), today) == (today, today)
    assert resolve_period(date(2025, 10, 9), today, today) == (date(2025, 10, 9), today)
    with pytest.raises(InvalidReportPeriodError, match="anterior"):
        resolve_period(date(2026, 10, 10), today, today)
    with pytest.raises(InvalidReportPeriodError, match="366"):
        resolve_period(date(2025, 10, 8), today, today)


def test_iso_weeks_across_year_boundary() -> None:
    assert [w for w, _ in iso_weeks(date(2026, 12, 28), date(2027, 1, 11))] == [
        "2026-W53",
        "2027-W01",
        "2027-W02",
    ]
    assert [w for w, _ in iso_weeks(date(2027, 1, 3), date(2027, 1, 3))] == ["2026-W53"]


def test_period_bounds_use_report_timezone() -> None:
    start, end = period_bounds(date(2026, 9, 1), date(2026, 9, 1))
    assert start.astimezone(UTC) == datetime(2026, 9, 1, 3, tzinfo=UTC)
    assert end.astimezone(UTC) == datetime(2026, 9, 2, 3, tzinfo=UTC)


def test_aggregate_ignores_messages_of_unknown_conversations() -> None:
    conv = _conv(PROTEUS, "ana@linx.com", "x", set())
    report = aggregate_report(
        workspaces=[PROTEUS],
        conversations=[conv],
        messages=[_msg(conv, NOW, 1.0), ReportMessage(uuid.uuid4(), NOW, 5.0)],
        start=date(2026, 10, 9),
        end=date(2026, 10, 9),
    )
    assert report.totals.cost_usd == 1.0
    assert report.themes[0].key == "outros"


def test_branches_from_repos_reads_base_and_work_branch() -> None:
    repos = [
        {"base_branch": "main", "branch_name": None},
        {"base_branch": "master", "branch_name": "cappy/fix-1"},
        {"base_branch": "  "},
        "lixo",
    ]
    assert branches_from_repos(repos) == {"main", "master", "cappy/fix-1"}
    assert branches_from_repos(None) == frozenset()


async def test_options_list_visible_workspaces_and_scope_branches(
    repo: InMemoryWorkspaceReportRepository,
) -> None:
    options = await GetWorkspaceReportOptions(repo).execute(SUPER, PROTEUS.id)
    assert [w.slug for w in options.workspaces] == ["proteus", "seller"]
    assert options.branches == ["main", "release"]
    assert options.can_edit_themes is True
    every = await GetWorkspaceReportOptions(repo).execute(SUPER, None)
    assert every.branches == ["main", "master", "release"]


async def test_theme_update_requires_super_admin_and_valid_rules(
    repo: InMemoryWorkspaceReportRepository,
) -> None:
    admin = ReportViewer(user_id=uuid.uuid4(), is_super_admin=False)
    repo.grant(admin.user_id, PROTEUS.id)
    config = await GetWorkspaceReportThemes(repo).execute(admin, PROTEUS.id)
    assert (config.preset, config.custom, config.rules[0].key) == (
        "nfse-protheus",
        False,
        "nfse-emissor-nacional",
    )
    update = UpdateWorkspaceReportThemes(repo)
    with pytest.raises(WorkspaceReportAccessDeniedError):
        await update.execute(admin, PROTEUS.id, preset=None, rules=None)
    with pytest.raises(InvalidThemeRulesError):
        await update.execute(SUPER, PROTEUS.id, preset="nao-existe", rules=None)
    with pytest.raises(InvalidThemeRulesError):
        await update.execute(SUPER, PROTEUS.id, preset=None, rules=[{"key": "x"}])
    saved = await update.execute(
        SUPER,
        PROTEUS.id,
        preset="nfse-protheus",
        rules=[{"key": "ola", "label": "Olá", "patterns": ["ola"]}],
    )
    assert (saved.custom, [r.key for r in saved.rules]) == (True, ["ola"])
    themes = (await _build(repo, start=date(2026, 8, 31))).report.themes
    assert [t.key for t in themes] == ["ola", "outros"]
    reset = await update.execute(SUPER, PROTEUS.id, preset=None, rules=None)
    assert (reset.preset, reset.custom, reset.rules[0].key) == ("generico", False, "desempenho")
