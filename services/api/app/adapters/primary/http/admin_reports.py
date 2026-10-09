"""Admin: relatório de uso por workspace (consultas, analistas, custo, semanas, temas).

  GET /admin/reports/options?workspace_id=            → workspaces visíveis e branches
  GET /admin/reports/workspace?workspace_id&branch&start&end
  GET /admin/reports/workspace/export?format=xlsx|csv&…
  GET /admin/reports/themes/{workspace_id}            → temas em vigor
  PUT /admin/reports/themes/{workspace_id}            → só super admin

Custo é sempre a soma de ``messages.cost_usd``. Admin comum só vê os
workspaces que tem em ``user_workspace_access``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http._admin_reports_export import (
    export_filename,
    report_csv,
    report_xlsx,
)
from app.adapters.primary.http.deps import get_db_session, require_role
from app.adapters.secondary.persistence.sqlalchemy_workspace_report_repo import (
    SQLAlchemyWorkspaceReportRepository,
)
from app.application.use_cases.workspace_report import (
    BuildWorkspaceReport,
    BuiltReport,
    GetWorkspaceReportOptions,
    GetWorkspaceReportThemes,
    InvalidReportPeriodError,
    ReportViewer,
    ThemeConfig,
    UpdateWorkspaceReportThemes,
    WorkspaceReportAccessDeniedError,
    WorkspaceReportNotFoundError,
)
from app.domain.entities import User, UserRole
from app.domain.report_themes import InvalidThemeRulesError
from app.ports.workspace_report import WorkspaceReportRepository

router = APIRouter(prefix="/admin/reports", tags=["admin"])

Admin = Annotated[User, Depends(require_role(UserRole.ADMIN))]


def get_workspace_report_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> WorkspaceReportRepository:
    return SQLAlchemyWorkspaceReportRepository(session)


Repo = Annotated[WorkspaceReportRepository, Depends(get_workspace_report_repo)]


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class WorkspaceOptionOut(_Out):
    id: uuid.UUID
    slug: str
    name: str


class ReportOptionsOut(_Out):
    workspaces: list[WorkspaceOptionOut]
    branches: list[str]
    can_edit_themes: bool


class ReportFiltersOut(_Out):
    workspace_id: uuid.UUID | None
    workspace_name: str | None
    branch: str | None
    start: date
    end: date
    timezone: str
    currency: Literal["USD"] = "USD"


class ReportTotalsOut(_Out):
    consultations: int
    analysts: int
    messages: int
    cost_usd: float
    avg_cost_per_consultation: float
    avg_cost_per_analyst: float


class AnalystOut(_Out):
    email: str
    label: str
    consultations: int
    cost_usd: float
    avg_cost_usd: float


class WeekOut(_Out):
    week: str
    start: date
    consultations: int
    cost_usd: float


class ThemeOut(_Out):
    key: str
    label: str
    consultations: int
    cost_usd: float


class WorkspaceTotalsOut(_Out):
    id: uuid.UUID
    slug: str
    name: str
    consultations: int
    cost_usd: float


class ConsultationOut(_Out):
    conversation_id: uuid.UUID
    workspace_slug: str
    analyst_email: str
    ticket_number: str | None
    title: str
    theme_key: str
    theme_label: str
    branches: list[str]
    messages: int
    cost_usd: float
    first_message_at: datetime
    last_message_at: datetime


class WorkspaceReportOut(BaseModel):
    generated_at: datetime
    filters: ReportFiltersOut
    totals: ReportTotalsOut
    analysts: list[AnalystOut]
    weeks: list[WeekOut]
    themes: list[ThemeOut]
    workspaces: list[WorkspaceTotalsOut]
    consultations: list[ConsultationOut]


class ThemeRuleOut(_Out):
    key: str
    label: str
    patterns: list[str]


class ThemePresetOut(BaseModel):
    key: str
    label: str


class ThemeConfigOut(BaseModel):
    workspace_id: uuid.UUID
    preset: str | None
    custom: bool
    rules: list[ThemeRuleOut]
    presets: list[ThemePresetOut]


class ThemeConfigIn(BaseModel):
    preset: str | None = None
    rules: list[dict[str, Any]] | None = None


def _viewer(user: User) -> ReportViewer:
    return ReportViewer(user_id=user.id, is_super_admin=user.is_super_admin)


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, WorkspaceReportAccessDeniedError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, WorkspaceReportNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


_REPORT_ERRORS = (
    WorkspaceReportAccessDeniedError,
    WorkspaceReportNotFoundError,
    InvalidReportPeriodError,
    InvalidThemeRulesError,
)


def _report_out(built: BuiltReport) -> WorkspaceReportOut:
    report = built.report
    return WorkspaceReportOut(
        generated_at=built.generated_at,
        filters=ReportFiltersOut.model_validate(built),
        totals=ReportTotalsOut.model_validate(report.totals),
        analysts=[AnalystOut.model_validate(a) for a in report.analysts],
        weeks=[WeekOut.model_validate(w) for w in report.weeks],
        themes=[ThemeOut.model_validate(t) for t in report.themes],
        workspaces=[WorkspaceTotalsOut.model_validate(w) for w in report.workspaces],
        consultations=[ConsultationOut.model_validate(c) for c in report.consultations],
    )


def _themes_out(config: ThemeConfig) -> ThemeConfigOut:
    return ThemeConfigOut(
        workspace_id=config.workspace_id,
        preset=config.preset,
        custom=config.custom,
        rules=[ThemeRuleOut.model_validate(rule.as_dict()) for rule in config.rules],
        presets=[ThemePresetOut(key=key, label=label) for key, label in config.presets],
    )


async def _build(
    repo: WorkspaceReportRepository,
    user: User,
    workspace_id: uuid.UUID | None,
    branch: str | None,
    start: date | None,
    end: date | None,
) -> BuiltReport:
    try:
        return await BuildWorkspaceReport(repo).execute(
            _viewer(user),
            workspace_id=workspace_id,
            branch=branch,
            start=start,
            end=end,
            now=datetime.now(UTC),
        )
    except _REPORT_ERRORS as exc:
        raise _http_error(exc) from exc


@router.get("/options", response_model=ReportOptionsOut)
async def get_report_options(
    user: Admin, repo: Repo, workspace_id: uuid.UUID | None = None
) -> ReportOptionsOut:
    try:
        options = await GetWorkspaceReportOptions(repo).execute(_viewer(user), workspace_id)
    except _REPORT_ERRORS as exc:
        raise _http_error(exc) from exc
    return ReportOptionsOut.model_validate(options)


@router.get("/workspace", response_model=WorkspaceReportOut)
async def get_workspace_report(
    user: Admin,
    repo: Repo,
    workspace_id: uuid.UUID | None = None,
    branch: str | None = Query(default=None, max_length=256),
    start: date | None = None,
    end: date | None = None,
) -> WorkspaceReportOut:
    return _report_out(await _build(repo, user, workspace_id, branch, start, end))


@router.get("/workspace/export")
async def export_workspace_report(
    user: Admin,
    repo: Repo,
    workspace_id: uuid.UUID | None = None,
    branch: str | None = Query(default=None, max_length=256),
    start: date | None = None,
    end: date | None = None,
    format: Literal["xlsx", "csv"] = "xlsx",
) -> Response:
    built = await _build(repo, user, workspace_id, branch, start, end)
    if format == "csv":
        content, media = report_csv(built), "text/csv; charset=utf-8"
    else:
        content = report_xlsx(built)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return Response(
        content=content,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{export_filename(built, format)}"'},
    )


@router.get("/themes/{workspace_id}", response_model=ThemeConfigOut)
async def get_report_themes(user: Admin, repo: Repo, workspace_id: uuid.UUID) -> ThemeConfigOut:
    try:
        config = await GetWorkspaceReportThemes(repo).execute(_viewer(user), workspace_id)
    except _REPORT_ERRORS as exc:
        raise _http_error(exc) from exc
    return _themes_out(config)


@router.put("/themes/{workspace_id}", response_model=ThemeConfigOut)
async def update_report_themes(
    user: Admin, repo: Repo, workspace_id: uuid.UUID, body: ThemeConfigIn
) -> ThemeConfigOut:
    try:
        config = await UpdateWorkspaceReportThemes(repo).execute(
            _viewer(user), workspace_id, preset=body.preset, rules=body.rules
        )
    except _REPORT_ERRORS as exc:
        raise _http_error(exc) from exc
    return _themes_out(config)
