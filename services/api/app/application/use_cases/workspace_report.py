"""Relatório de uso por workspace: escopo visível, filtros, opções e temas.

Super admin enxerga todos os workspaces; admin comum só os que tem em
``user_workspace_access``. Pedir um workspace fora disso é acesso negado.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from app.application.use_cases._workspace_report_metrics import (
    REPORT_TZ,
    WorkspaceReport,
    aggregate_report,
    period_bounds,
)
from app.domain.report_themes import (
    DEFAULT_PRESET,
    PRESETS,
    InvalidThemeRulesError,
    ThemeRule,
    preset_choices,
    resolve_rules,
    validate_theme_rules,
)
from app.ports.workspace_report import ReportWorkspace, WorkspaceReportRepository

MAX_PERIOD_DAYS = 366
DEFAULT_PERIOD_DAYS = 30


class WorkspaceReportAccessDeniedError(Exception):
    """Admin sem acesso ao workspace pedido (ou sem super admin para editar temas)."""


class WorkspaceReportNotFoundError(Exception):
    """Workspace inexistente."""


class InvalidReportPeriodError(ValueError):
    """Período fora das regras (início depois do fim ou longo demais)."""


@dataclass(frozen=True)
class ReportViewer:
    user_id: uuid.UUID
    is_super_admin: bool


@dataclass(frozen=True)
class ReportOptions:
    workspaces: list[ReportWorkspace]
    branches: list[str]
    can_edit_themes: bool


@dataclass(frozen=True)
class BuiltReport:
    generated_at: datetime
    workspace_id: uuid.UUID | None
    workspace_name: str | None
    scope_slug: str
    branch: str | None
    start: date
    end: date
    timezone: str
    report: WorkspaceReport


@dataclass(frozen=True)
class ThemeConfig:
    workspace_id: uuid.UUID
    preset: str | None
    custom: bool
    rules: tuple[ThemeRule, ...]
    presets: list[tuple[str, str]]


def resolve_period(start: date | None, end: date | None, today: date) -> tuple[date, date]:
    """Sem datas: últimos 30 dias até hoje. Valida ordem e tamanho."""
    end = end or today
    start = start or end - timedelta(days=DEFAULT_PERIOD_DAYS - 1)
    if start > end:
        raise InvalidReportPeriodError("A data inicial deve ser anterior ou igual à final.")
    if (end - start).days + 1 > MAX_PERIOD_DAYS:
        raise InvalidReportPeriodError(f"O período pode ter no máximo {MAX_PERIOD_DAYS} dias.")
    return start, end


async def visible_workspaces(
    repo: WorkspaceReportRepository, viewer: ReportViewer
) -> list[ReportWorkspace]:
    workspaces = await repo.list_workspaces()
    if viewer.is_super_admin:
        return workspaces
    allowed = await repo.accessible_workspace_ids(viewer.user_id)
    return [ws for ws in workspaces if ws.id in allowed]


async def resolve_scope(
    repo: WorkspaceReportRepository, viewer: ReportViewer, workspace_id: uuid.UUID | None
) -> list[ReportWorkspace]:
    """Workspaces do relatório: o pedido (se visível) ou todos os visíveis."""
    visible = await visible_workspaces(repo, viewer)
    if workspace_id is None:
        return visible
    chosen = [ws for ws in visible if ws.id == workspace_id]
    if chosen:
        return chosen
    if any(ws.id == workspace_id for ws in await repo.list_workspaces()):
        raise WorkspaceReportAccessDeniedError("Sem acesso a este workspace.")
    raise WorkspaceReportNotFoundError("Workspace não encontrado.")


class GetWorkspaceReportOptions:
    def __init__(self, repo: WorkspaceReportRepository) -> None:
        self._repo = repo

    async def execute(self, viewer: ReportViewer, workspace_id: uuid.UUID | None) -> ReportOptions:
        scope = await resolve_scope(self._repo, viewer, workspace_id)
        return ReportOptions(
            workspaces=await visible_workspaces(self._repo, viewer),
            branches=await self._repo.list_branches([ws.id for ws in scope]),
            can_edit_themes=viewer.is_super_admin,
        )


class BuildWorkspaceReport:
    def __init__(self, repo: WorkspaceReportRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        viewer: ReportViewer,
        *,
        workspace_id: uuid.UUID | None,
        branch: str | None,
        start: date | None,
        end: date | None,
        now: datetime,
    ) -> BuiltReport:
        start, end = resolve_period(start, end, now.astimezone(REPORT_TZ).date())
        scope = await resolve_scope(self._repo, viewer, workspace_id)
        branch = (branch or "").strip() or None
        since, until = period_bounds(start, end)
        messages = await self._repo.list_period_messages([ws.id for ws in scope], since, until)
        conversations = await self._repo.get_conversations(
            sorted({msg.conversation_id for msg in messages})
        )
        report = aggregate_report(
            workspaces=scope,
            conversations=conversations,
            messages=messages,
            start=start,
            end=end,
            branch=branch,
        )
        single = scope[0] if workspace_id is not None else None
        return BuiltReport(
            generated_at=now,
            workspace_id=workspace_id,
            workspace_name=single.name if single else None,
            scope_slug=single.slug if single else "todos",
            branch=branch,
            start=start,
            end=end,
            timezone=str(REPORT_TZ),
            report=report,
        )


def _theme_config(ws: ReportWorkspace) -> ThemeConfig:
    return ThemeConfig(
        workspace_id=ws.id,
        preset=ws.theme_preset or DEFAULT_PRESET,
        custom=bool(ws.theme_rules),
        rules=resolve_rules(ws.theme_preset, ws.theme_rules),
        presets=preset_choices(),
    )


class GetWorkspaceReportThemes:
    def __init__(self, repo: WorkspaceReportRepository) -> None:
        self._repo = repo

    async def execute(self, viewer: ReportViewer, workspace_id: uuid.UUID) -> ThemeConfig:
        (ws,) = await resolve_scope(self._repo, viewer, workspace_id)
        return _theme_config(ws)


class UpdateWorkspaceReportThemes:
    """Só super admin. Regras próprias valem sobre o modelo; sem elas, vale o modelo."""

    def __init__(self, repo: WorkspaceReportRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        viewer: ReportViewer,
        workspace_id: uuid.UUID,
        *,
        preset: str | None,
        rules: list[Any] | None,
    ) -> ThemeConfig:
        if not viewer.is_super_admin:
            raise WorkspaceReportAccessDeniedError("Só o super admin edita os temas.")
        await resolve_scope(self._repo, viewer, workspace_id)
        if preset is not None and preset not in PRESETS:
            raise InvalidThemeRulesError(f"Modelo de temas desconhecido: {preset}.")
        stored = None
        if rules is not None:
            stored = [rule.as_dict() for rule in validate_theme_rules(rules)]
        saved = await self._repo.save_theme_config(workspace_id, preset, stored)
        if saved is None:
            raise WorkspaceReportNotFoundError("Workspace não encontrado.")
        return _theme_config(saved)
