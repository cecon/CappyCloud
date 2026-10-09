"""Relatório de uso: agregação, período, semanas, R$ e escopo de acesso (fakes)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest
from app.application.use_cases._workspace_report_metrics import (
    REPORT_TZ,
    aggregate_report,
    period_bounds,
    period_weeks,
    week_label,
)
from app.application.use_cases.workspace_report import (
    BuildWorkspaceReport,
    BuiltReport,
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

from tests.fakes_reports import FakeUsdBrlRateProvider, InMemoryWorkspaceReportRepository

PROTEUS = ReportWorkspace(uuid.uuid4(), "proteus", "PROTEUS", theme_preset="nfse-detalhado")
SELLER = ReportWorkspace(uuid.uuid4(), "seller", "SELLER")
SUPER = ReportViewer(user_id=uuid.uuid4(), is_super_admin=True)
NOW = datetime(2026, 10, 9, 15, 0, tzinfo=UTC)


def _local(*args: int) -> datetime:
    return datetime(*args, tzinfo=REPORT_TZ).astimezone(UTC)


def _conv(ws: ReportWorkspace, email: str, title: str, branches: set[str]) -> ReportConversation:
    return ReportConversation(uuid.uuid4(), ws.id, email, title, branches=frozenset(branches))


def _ask(conv: ReportConversation, when: datetime) -> ReportMessage:
    return ReportMessage(conv.id, when, 0.0, is_question=True)


def _answer(conv: ReportConversation, when: datetime, cost: float) -> ReportMessage:
    return ReportMessage(conv.id, when, cost)


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
        a,
        _ask(a, _local(2026, 9, 1, 10)),
        _answer(a, _local(2026, 9, 1, 10, 1), 1.0),
        _ask(a, _local(2026, 9, 8, 9)),
        _answer(a, _local(2026, 9, 8, 9, 1), 0.5),
    )
    repo.add_conversation(
        b, _ask(b, _local(2026, 9, 7, 23, 58)), _answer(b, _local(2026, 9, 7, 23, 59), 2.0)
    )
    # Só antes do período: não conta.
    repo.add_conversation(
        c, _ask(c, _local(2026, 8, 31, 23, 58)), _answer(c, _local(2026, 8, 31, 23, 59), 9.0)
    )
    repo.add_conversation(
        s, _ask(s, _local(2026, 9, 2, 8)), _answer(s, _local(2026, 9, 2, 8, 1), 4.0)
    )
    return repo


async def _build(
    repo: InMemoryWorkspaceReportRepository, viewer: ReportViewer = SUPER, **kw: object
) -> BuiltReport:
    params: dict[str, object] = {
        "workspace_id": PROTEUS.id,
        "branch": None,
        "start": date(2026, 9, 1),
        "end": date(2026, 9, 8),
        "now": NOW,
    }
    rates = kw.pop("rates", None)
    params.update(kw)
    return await BuildWorkspaceReport(repo, rates).execute(viewer, **params)  # type: ignore[arg-type]


async def test_questions_are_the_report_consultations(
    repo: InMemoryWorkspaceReportRepository,
) -> None:
    built = await _build(repo)
    t = built.report.totals
    assert (t.questions, t.conversations, t.analysts, t.messages) == (3, 2, 2, 6)
    assert t.cost_usd == 3.5
    assert t.avg_cost_per_question == round(3.5 / 3, 6)
    assert t.avg_cost_per_conversation == 1.75
    assert t.avg_cost_per_analyst == 1.75
    assert (built.scope_slug, built.workspace_name, built.brl) == ("proteus", "PROTEUS", None)


async def test_period_end_is_inclusive_until_midnight_local(
    repo: InMemoryWorkspaceReportRepository,
) -> None:
    built = await _build(repo, start=date(2026, 9, 7), end=date(2026, 9, 7))
    assert [c.title for c in built.report.conversations] == ["Falha de schema SP indDest"]
    built = await _build(repo, start=date(2026, 8, 31), end=date(2026, 8, 31))
    assert [c.title for c in built.report.conversations] == ["ola"]


async def test_analysts_table_uses_email_and_part_before_at(
    repo: InMemoryWorkspaceReportRepository,
) -> None:
    analysts = (await _build(repo)).report.analysts
    assert [(a.email, a.label, a.questions, a.conversations, a.cost_usd) for a in analysts] == [
        ("ana@linx.com", "ana", 2, 1, 1.5),
        ("bruno@linx.com", "bruno", 1, 1, 2.0),
    ]
    assert analysts[0].avg_cost_per_question == 0.75


async def test_weeks_are_seven_day_blocks_from_period_start(
    repo: InMemoryWorkspaceReportRepository,
) -> None:
    weeks = (await _build(repo, end=date(2026, 9, 16))).report.weeks
    assert [(w.label, w.start, w.end, w.questions, w.cost_usd) for w in weeks] == [
        ("01-07/09", date(2026, 9, 1), date(2026, 9, 7), 2, 3.0),
        ("08-14/09", date(2026, 9, 8), date(2026, 9, 14), 1, 0.5),
        ("15-16/09", date(2026, 9, 15), date(2026, 9, 16), 0, 0.0),
    ]


def test_week_labels_and_blocks() -> None:
    assert week_label(date(2026, 9, 29), date(2026, 10, 5)) == "29/09-05/10"
    assert week_label(date(2026, 10, 6), date(2026, 10, 8)) == "06-08/10"
    blocks = period_weeks(date(2026, 9, 1), date(2026, 10, 8))
    assert len(blocks) == 6
    assert blocks[-1] == (date(2026, 10, 6), date(2026, 10, 8))
    assert period_weeks(date(2026, 9, 1), date(2026, 9, 7)) == [
        (date(2026, 9, 1), date(2026, 9, 7))
    ]
    assert period_weeks(date(2026, 9, 1), date(2026, 9, 1)) == [
        (date(2026, 9, 1), date(2026, 9, 1))
    ]


async def test_themes_share_is_over_questions(repo: InMemoryWorkspaceReportRepository) -> None:
    themes = (await _build(repo)).report.themes
    assert [(t.key, t.questions, t.share, t.cost_usd) for t in themes] == [
        ("nfse-retencoes", 2, 0.6667, 1.5),
        ("nfse-schema-xml", 1, 0.3333, 2.0),
    ]


async def test_branch_filter_keeps_only_matching_conversations(
    repo: InMemoryWorkspaceReportRepository,
) -> None:
    built = await _build(repo, branch=" release ", start=date(2026, 8, 1))
    assert built.branch == "release"
    assert [c.title for c in built.report.conversations] == ["ola"]
    assert (await _build(repo, branch="nao-existe")).report.totals.questions == 0


async def test_all_workspaces_for_super_admin_breaks_down_per_workspace(
    repo: InMemoryWorkspaceReportRepository,
) -> None:
    built = await _build(repo, workspace_id=None)
    assert (built.scope_slug, built.workspace_name) == ("todos", None)
    assert built.report.totals.questions == 4
    rows = [(w.slug, w.questions, w.conversations, w.cost_usd) for w in built.report.workspaces]
    assert rows == [("proteus", 3, 2, 3.5), ("seller", 1, 1, 4.0)]
    # Cada workspace usa os próprios temas (seller cai no modelo genérico).
    assert {t.key for t in built.report.themes} == {
        "nfse-schema-xml",
        "nfse-retencoes",
        "configuracoes",
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
    assert (await _build(repo, nobody, workspace_id=None)).report.totals.questions == 0


async def test_empty_period_has_zero_averages(repo: InMemoryWorkspaceReportRepository) -> None:
    t = (await _build(repo, start=date(2025, 1, 1), end=date(2025, 1, 5))).report.totals
    assert (t.questions, t.cost_usd, t.avg_cost_per_question) == (0, 0.0, 0.0)
    assert (t.avg_cost_per_conversation, t.avg_cost_per_analyst) == (0.0, 0.0)


async def test_brl_rate_comes_from_last_quote_until_period_end(
    repo: InMemoryWorkspaceReportRepository,
) -> None:
    rates = FakeUsdBrlRateProvider({date(2026, 9, 4): 5.2, date(2026, 9, 9): 5.0})
    built = await _build(repo, rates=rates)
    assert built.brl is not None
    assert (built.brl.rate, built.brl.quoted_on) == (5.2, date(2026, 9, 4))
    assert rates.asked == [date(2026, 9, 8)]
    # Período que termina no futuro pede a cotação de hoje.
    await _build(repo, rates=rates, end=date(2026, 12, 31))
    assert rates.asked[-1] == date(2026, 10, 9)
    assert (await _build(repo, rates=FakeUsdBrlRateProvider())).brl is None


def test_resolve_period_defaults_and_limits() -> None:
    today = date(2026, 10, 9)
    assert resolve_period(None, None, today) == (date(2026, 9, 10), today)
    assert resolve_period(date(2026, 10, 9), date(2026, 10, 9), today) == (today, today)
    assert resolve_period(date(2025, 10, 9), today, today) == (date(2025, 10, 9), today)
    with pytest.raises(InvalidReportPeriodError, match="anterior"):
        resolve_period(date(2026, 10, 10), today, today)
    with pytest.raises(InvalidReportPeriodError, match="366"):
        resolve_period(date(2025, 10, 8), today, today)


def test_period_bounds_use_report_timezone() -> None:
    start, end = period_bounds(date(2026, 9, 1), date(2026, 9, 1))
    assert start.astimezone(UTC) == datetime(2026, 9, 1, 3, tzinfo=UTC)
    assert end.astimezone(UTC) == datetime(2026, 9, 2, 3, tzinfo=UTC)


def test_aggregate_ignores_messages_of_unknown_conversations() -> None:
    conv = _conv(PROTEUS, "ana@linx.com", "x", set())
    report = aggregate_report(
        workspaces=[PROTEUS],
        conversations=[conv],
        messages=[_answer(conv, NOW, 1.0), ReportMessage(uuid.uuid4(), NOW, 5.0, True)],
        start=date(2026, 10, 9),
        end=date(2026, 10, 9),
    )
    assert (report.totals.cost_usd, report.totals.questions) == (1.0, 0)
    assert (report.themes[0].key, report.themes[0].share) == ("outros", 0.0)


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
        "nfse-detalhado",
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
    custom = [{"key": "ola", "label": "Olá", "patterns": ["ola"]}]
    saved = await update.execute(SUPER, PROTEUS.id, preset="protheus-tss", rules=custom)
    assert (saved.custom, [r.key for r in saved.rules]) == (True, ["ola"])
    themes = (await _build(repo, start=date(2026, 8, 31))).report.themes
    assert [t.key for t in themes] == ["ola", "outros"]
    reset = await update.execute(SUPER, PROTEUS.id, preset=None, rules=None)
    assert (reset.preset, reset.custom, reset.rules[0].key) == (
        "generico",
        False,
        "erros-rejeicoes",
    )
