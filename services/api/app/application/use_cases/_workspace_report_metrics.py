"""Cálculo do relatório de uso: função pura sobre os dados crus da port.

Consulta = conversa do escopo com ao menos uma mensagem no período. Custo =
soma de ``messages.cost_usd`` das mensagens do período (dado do provedor).
Datas e semanas ISO no fuso do relatório.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.domain.report_themes import OTHER_THEME_KEY, ThemeClassifier, resolve_rules
from app.ports.workspace_report import ReportConversation, ReportMessage, ReportWorkspace

REPORT_TZ = ZoneInfo("America/Sao_Paulo")
_COST_DIGITS = 6


@dataclass(frozen=True)
class ReportTotals:
    consultations: int
    analysts: int
    messages: int
    cost_usd: float
    avg_cost_per_consultation: float
    avg_cost_per_analyst: float


@dataclass(frozen=True)
class AnalystRow:
    email: str
    label: str
    consultations: int
    cost_usd: float
    avg_cost_usd: float


@dataclass(frozen=True)
class WeekRow:
    week: str
    start: date
    consultations: int
    cost_usd: float


@dataclass(frozen=True)
class ThemeRow:
    key: str
    label: str
    consultations: int
    cost_usd: float


@dataclass(frozen=True)
class WorkspaceRow:
    id: uuid.UUID
    slug: str
    name: str
    consultations: int
    cost_usd: float


@dataclass(frozen=True)
class ConsultationRow:
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


@dataclass(frozen=True)
class WorkspaceReport:
    totals: ReportTotals
    analysts: list[AnalystRow]
    weeks: list[WeekRow]
    themes: list[ThemeRow]
    workspaces: list[WorkspaceRow]
    consultations: list[ConsultationRow]


def period_bounds(start: date, end: date, tz: ZoneInfo = REPORT_TZ) -> tuple[datetime, datetime]:
    """Início do dia ``start`` e início do dia seguinte a ``end`` (exclusivo), com fuso."""
    return (
        datetime.combine(start, time.min, tzinfo=tz),
        datetime.combine(end + timedelta(days=1), time.min, tzinfo=tz),
    )


def week_label(day: date) -> str:
    iso = day.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def iso_weeks(start: date, end: date) -> list[tuple[str, date]]:
    """Todas as semanas ISO (rótulo, segunda-feira) que tocam o período."""
    monday = start - timedelta(days=start.weekday())
    weeks: list[tuple[str, date]] = []
    while monday <= end:
        weeks.append((week_label(monday), monday))
        monday += timedelta(days=7)
    return weeks


def _money(value: float) -> float:
    return round(value, _COST_DIGITS)


def _avg(total: float, count: int) -> float:
    return _money(total / count) if count else 0.0


def _analyst_label(email: str) -> str:
    return email.split("@", 1)[0] or email


def _consultations(
    workspaces: Sequence[ReportWorkspace],
    conversations: Sequence[ReportConversation],
    messages: Sequence[ReportMessage],
    branch: str | None,
    tz: ZoneInfo,
) -> tuple[list[ConsultationRow], dict[uuid.UUID, list[ReportMessage]]]:
    by_ws = {ws.id: ws for ws in workspaces}
    classifiers = {
        ws.id: ThemeClassifier(resolve_rules(ws.theme_preset, ws.theme_rules)) for ws in workspaces
    }
    in_scope = {
        conv.id: conv
        for conv in conversations
        if conv.workspace_id in by_ws and (branch is None or branch in conv.branches)
    }
    grouped: dict[uuid.UUID, list[ReportMessage]] = defaultdict(list)
    for msg in messages:
        if msg.conversation_id in in_scope:
            grouped[msg.conversation_id].append(msg)
    rows: list[ConsultationRow] = []
    for conv_id, msgs in grouped.items():
        conv = in_scope[conv_id]
        theme_key, theme_label = classifiers[conv.workspace_id].classify(
            f"{conv.title}\n{conv.first_user_message}"
        )
        rows.append(
            ConsultationRow(
                conversation_id=conv.id,
                workspace_slug=by_ws[conv.workspace_id].slug,
                analyst_email=conv.user_email,
                ticket_number=conv.ticket_number,
                title=conv.title,
                theme_key=theme_key,
                theme_label=theme_label,
                branches=sorted(conv.branches),
                messages=len(msgs),
                cost_usd=_money(sum(m.cost_usd for m in msgs)),
                first_message_at=min(m.created_at for m in msgs).astimezone(tz),
                last_message_at=max(m.created_at for m in msgs).astimezone(tz),
            )
        )
    rows.sort(key=lambda row: row.last_message_at, reverse=True)
    return rows, grouped


def _weeks(
    grouped: dict[uuid.UUID, list[ReportMessage]], start: date, end: date, tz: ZoneInfo
) -> list[WeekRow]:
    convs: dict[str, set[uuid.UUID]] = defaultdict(set)
    costs: dict[str, float] = defaultdict(float)
    for conv_id, msgs in grouped.items():
        for msg in msgs:
            label = week_label(msg.created_at.astimezone(tz).date())
            convs[label].add(conv_id)
            costs[label] += msg.cost_usd
    return [
        WeekRow(
            week=label, start=monday, consultations=len(convs[label]), cost_usd=_money(costs[label])
        )
        for label, monday in iso_weeks(start, end)
    ]


def _group_rows(rows: Sequence[ConsultationRow], key: str) -> dict[str, tuple[int, float]]:
    totals: dict[str, tuple[int, float]] = {}
    for row in rows:
        value = getattr(row, key)
        count, cost = totals.get(value, (0, 0.0))
        totals[value] = (count + 1, cost + row.cost_usd)
    return totals


def aggregate_report(
    *,
    workspaces: Sequence[ReportWorkspace],
    conversations: Sequence[ReportConversation],
    messages: Sequence[ReportMessage],
    start: date,
    end: date,
    branch: str | None = None,
    tz: ZoneInfo = REPORT_TZ,
) -> WorkspaceReport:
    rows, grouped = _consultations(workspaces, conversations, messages, branch, tz)
    total_cost = sum(row.cost_usd for row in rows)

    analysts = [
        AnalystRow(
            email=email,
            label=_analyst_label(email),
            consultations=count,
            cost_usd=_money(cost),
            avg_cost_usd=_avg(cost, count),
        )
        for email, (count, cost) in _group_rows(rows, "analyst_email").items()
    ]
    analysts.sort(key=lambda a: (-a.cost_usd, -a.consultations, a.email))

    labels = {row.theme_key: row.theme_label for row in rows}
    themes = [
        ThemeRow(key=key, label=labels[key], consultations=count, cost_usd=_money(cost))
        for key, (count, cost) in _group_rows(rows, "theme_key").items()
    ]
    themes.sort(key=lambda t: (t.key == OTHER_THEME_KEY, -t.consultations, -t.cost_usd, t.label))

    per_ws = _group_rows(rows, "workspace_slug")
    ws_rows = [
        WorkspaceRow(
            id=ws.id,
            slug=ws.slug,
            name=ws.name,
            consultations=per_ws.get(ws.slug, (0, 0.0))[0],
            cost_usd=_money(per_ws.get(ws.slug, (0, 0.0))[1]),
        )
        for ws in workspaces
    ]

    totals = ReportTotals(
        consultations=len(rows),
        analysts=len(analysts),
        messages=sum(row.messages for row in rows),
        cost_usd=_money(total_cost),
        avg_cost_per_consultation=_avg(total_cost, len(rows)),
        avg_cost_per_analyst=_avg(total_cost, len(analysts)),
    )
    return WorkspaceReport(
        totals=totals,
        analysts=analysts,
        weeks=_weeks(grouped, start, end, tz),
        themes=themes,
        workspaces=ws_rows,
        consultations=rows,
    )
