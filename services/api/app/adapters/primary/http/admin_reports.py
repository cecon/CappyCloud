"""Admin: relatório de uso por workspace (consultas, analistas, custo, semanas, temas).

  GET /admin/reports/options?workspace_id=            → workspaces visíveis e branches
  GET /admin/reports/workspace?workspace_id&branch&start&end
  GET /admin/reports/workspace/export?format=xlsx|csv&…
  GET /admin/reports/themes/{workspace_id}            → temas em vigor
  PUT /admin/reports/themes/{workspace_id}            → só super admin

Custo é sempre a soma de ``messages.cost_usd``; R$ usa a PTAX do Banco Central. Admin comum só vê os
workspaces que tem em ``user_workspace_access``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http._admin_reports_export import (
    export_filename,
    report_csv,
    report_xlsx,
)
from app.adapters.primary.http.admin_reports_schemas import (
    ReportOptionsOut,
    ThemeConfigIn,
    ThemeConfigOut,
    WorkspaceReportOut,
    report_out,
    themes_out,
)
from app.adapters.primary.http.deps import get_db_session, require_role
from app.adapters.secondary.bcb_ptax import BcbPtaxRateProvider
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
    UpdateWorkspaceReportThemes,
    WorkspaceReportAccessDeniedError,
    WorkspaceReportNotFoundError,
)
from app.domain.entities import User, UserRole
from app.domain.report_themes import InvalidThemeRulesError
from app.ports.exchange_rates import UsdBrlRateProvider
from app.ports.workspace_report import WorkspaceReportRepository

router = APIRouter(prefix="/admin/reports", tags=["admin"])

Admin = Annotated[User, Depends(require_role(UserRole.ADMIN))]


def get_workspace_report_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> WorkspaceReportRepository:
    return SQLAlchemyWorkspaceReportRepository(session)


Repo = Annotated[WorkspaceReportRepository, Depends(get_workspace_report_repo)]

# Uma instância por processo: o cache de cotações passadas fica entre requisições.
_PTAX = BcbPtaxRateProvider()


def get_usd_brl_rates() -> UsdBrlRateProvider:
    return _PTAX


Rates = Annotated[UsdBrlRateProvider, Depends(get_usd_brl_rates)]


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


async def _build(
    repo: WorkspaceReportRepository,
    rates: UsdBrlRateProvider,
    user: User,
    workspace_id: uuid.UUID | None,
    branch: str | None,
    start: date | None,
    end: date | None,
) -> BuiltReport:
    try:
        return await BuildWorkspaceReport(repo, rates).execute(
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
    rates: Rates,
    workspace_id: uuid.UUID | None = None,
    branch: str | None = Query(default=None, max_length=256),
    start: date | None = None,
    end: date | None = None,
) -> WorkspaceReportOut:
    return report_out(await _build(repo, rates, user, workspace_id, branch, start, end))


@router.get("/workspace/export")
async def export_workspace_report(
    user: Admin,
    repo: Repo,
    rates: Rates,
    workspace_id: uuid.UUID | None = None,
    branch: str | None = Query(default=None, max_length=256),
    start: date | None = None,
    end: date | None = None,
    format: Literal["xlsx", "csv"] = "xlsx",
) -> Response:
    built = await _build(repo, rates, user, workspace_id, branch, start, end)
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
    return themes_out(config)


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
    return themes_out(config)
