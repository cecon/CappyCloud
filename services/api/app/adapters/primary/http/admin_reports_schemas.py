"""Schemas HTTP de /admin/reports (relatório de uso por workspace)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.application.use_cases.workspace_report import BuiltReport, ThemeConfig


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


class BrlRateOut(_Out):
    rate: float
    quoted_on: date
    source: str


class ReportTotalsOut(_Out):
    questions: int
    conversations: int
    analysts: int
    messages: int
    cost_usd: float
    avg_cost_per_question: float
    avg_cost_per_conversation: float
    avg_cost_per_analyst: float


class AnalystOut(_Out):
    email: str
    label: str
    questions: int
    conversations: int
    cost_usd: float
    avg_cost_per_question: float


class WeekOut(_Out):
    start: date
    end: date
    label: str
    questions: int
    conversations: int
    cost_usd: float


class ThemeOut(_Out):
    key: str
    label: str
    questions: int
    conversations: int
    cost_usd: float
    share: float


class WorkspaceTotalsOut(_Out):
    id: uuid.UUID
    slug: str
    name: str
    questions: int
    conversations: int
    cost_usd: float


class ConversationOut(_Out):
    conversation_id: uuid.UUID
    workspace_slug: str
    analyst_email: str
    ticket_number: str | None
    title: str
    theme_key: str
    theme_label: str
    branches: list[str]
    questions: int
    messages: int
    cost_usd: float
    first_message_at: datetime
    last_message_at: datetime


class WorkspaceReportOut(BaseModel):
    generated_at: datetime
    filters: ReportFiltersOut
    brl: BrlRateOut | None
    totals: ReportTotalsOut
    analysts: list[AnalystOut]
    weeks: list[WeekOut]
    themes: list[ThemeOut]
    workspaces: list[WorkspaceTotalsOut]
    conversations: list[ConversationOut]


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


def report_out(built: BuiltReport) -> WorkspaceReportOut:
    report = built.report
    return WorkspaceReportOut(
        generated_at=built.generated_at,
        filters=ReportFiltersOut.model_validate(built),
        brl=BrlRateOut.model_validate(built.brl) if built.brl else None,
        totals=ReportTotalsOut.model_validate(report.totals),
        analysts=[AnalystOut.model_validate(a) for a in report.analysts],
        weeks=[WeekOut.model_validate(w) for w in report.weeks],
        themes=[ThemeOut.model_validate(t) for t in report.themes],
        workspaces=[WorkspaceTotalsOut.model_validate(w) for w in report.workspaces],
        conversations=[ConversationOut.model_validate(c) for c in report.conversations],
    )


def themes_out(config: ThemeConfig) -> ThemeConfigOut:
    return ThemeConfigOut(
        workspace_id=config.workspace_id,
        preset=config.preset,
        custom=config.custom,
        rules=[ThemeRuleOut.model_validate(rule.as_dict()) for rule in config.rules],
        presets=[ThemePresetOut(key=key, label=label) for key, label in config.presets],
    )
