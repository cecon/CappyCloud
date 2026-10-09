"""Cálculo do relatório de uso: função pura sobre os dados crus da port.

Consulta = pergunta do usuário (mensagem ``role='user'``) dentro do período,
como no relatório que o time leva à Diretoria. Conversa = conversa do escopo com
ao menos uma mensagem no período. Custo = soma de ``messages.cost_usd`` das
mensagens do período (dado do provedor). Semanas são blocos de 7 dias contados
a partir do início do período; o último pode ser menor.
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
    questions: int
    conversations: int
    analysts: int
    messages: int
    cost_usd: float
    avg_cost_per_question: float
    avg_cost_per_conversation: float
    avg_cost_per_analyst: float


@dataclass(frozen=True)
class AnalystRow:
    email: str
    label: str
    questions: int
    conversations: int
    cost_usd: float
    avg_cost_per_question: float


@dataclass(frozen=True)
class WeekRow:
    start: date
    end: date
    label: str
    questions: int
    conversations: int
    cost_usd: float


@dataclass(frozen=True)
class ThemeRow:
    key: str
    label: str
    questions: int
    conversations: int
    cost_usd: float
    share: float  # fração das perguntas do período (0 a 1)


@dataclass(frozen=True)
class WorkspaceRow:
    id: uuid.UUID
    slug: str
    name: str
    questions: int
    conversations: int
    cost_usd: float


@dataclass(frozen=True)
class ConversationRow:
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


@dataclass(frozen=True)
class WorkspaceReport:
    totals: ReportTotals
    analysts: list[AnalystRow]
    weeks: list[WeekRow]
    themes: list[ThemeRow]
    workspaces: list[WorkspaceRow]
    conversations: list[ConversationRow]


def period_bounds(start: date, end: date, tz: ZoneInfo = REPORT_TZ) -> tuple[datetime, datetime]:
    """Início do dia ``start`` e início do dia seguinte a ``end`` (exclusivo), com fuso."""
    return (
        datetime.combine(start, time.min, tzinfo=tz),
        datetime.combine(end + timedelta(days=1), time.min, tzinfo=tz),
    )


def week_label(start: date, end: date) -> str:
    """``01-07/09`` no mesmo mês; ``29/09-05/10`` quando vira o mês."""
    if start.month == end.month:
        return f"{start.day:02d}-{end.day:02d}/{end.month:02d}"
    return f"{start.day:02d}/{start.month:02d}-{end.day:02d}/{end.month:02d}"


def period_weeks(start: date, end: date) -> list[tuple[date, date]]:
    """Blocos de 7 dias a partir de ``start``; o último termina em ``end``."""
    weeks: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        weeks.append((cursor, min(cursor + timedelta(days=6), end)))
        cursor += timedelta(days=7)
    return weeks


def _money(value: float) -> float:
    return round(value, _COST_DIGITS)


def _avg(total: float, count: int) -> float:
    return _money(total / count) if count else 0.0


def _analyst_label(email: str) -> str:
    return email.split("@", 1)[0] or email


def _conversations(
    workspaces: Sequence[ReportWorkspace],
    conversations: Sequence[ReportConversation],
    messages: Sequence[ReportMessage],
    branch: str | None,
    tz: ZoneInfo,
) -> tuple[list[ConversationRow], dict[uuid.UUID, list[ReportMessage]]]:
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
    rows: list[ConversationRow] = []
    for conv_id, msgs in grouped.items():
        conv = in_scope[conv_id]
        theme_key, theme_label = classifiers[conv.workspace_id].classify(
            f"{conv.title}\n{conv.first_user_message}"
        )
        rows.append(
            ConversationRow(
                conversation_id=conv.id,
                workspace_slug=by_ws[conv.workspace_id].slug,
                analyst_email=conv.user_email,
                ticket_number=conv.ticket_number,
                title=conv.title,
                theme_key=theme_key,
                theme_label=theme_label,
                branches=sorted(conv.branches),
                questions=sum(1 for m in msgs if m.is_question),
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
    blocks = period_weeks(start, end)
    questions = [0] * len(blocks)
    costs = [0.0] * len(blocks)
    convs: list[set[uuid.UUID]] = [set() for _ in blocks]
    for conv_id, msgs in grouped.items():
        for msg in msgs:
            days = (msg.created_at.astimezone(tz).date() - start).days
            idx = min(max(days, 0) // 7, len(blocks) - 1)
            convs[idx].add(conv_id)
            costs[idx] += msg.cost_usd
            questions[idx] += msg.is_question
    return [
        WeekRow(
            start=first,
            end=last,
            label=week_label(first, last),
            questions=questions[idx],
            conversations=len(convs[idx]),
            cost_usd=_money(costs[idx]),
        )
        for idx, (first, last) in enumerate(blocks)
    ]


def _group_rows(rows: Sequence[ConversationRow], key: str) -> dict[str, tuple[int, int, float]]:
    """``valor da chave → (conversas, perguntas, custo)``."""
    totals: dict[str, tuple[int, int, float]] = {}
    for row in rows:
        value = getattr(row, key)
        convs, questions, cost = totals.get(value, (0, 0, 0.0))
        totals[value] = (convs + 1, questions + row.questions, cost + row.cost_usd)
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
    rows, grouped = _conversations(workspaces, conversations, messages, branch, tz)
    total_cost = sum(row.cost_usd for row in rows)
    total_questions = sum(row.questions for row in rows)

    analysts = [
        AnalystRow(
            email=email,
            label=_analyst_label(email),
            questions=questions,
            conversations=convs,
            cost_usd=_money(cost),
            avg_cost_per_question=_avg(cost, questions),
        )
        for email, (convs, questions, cost) in _group_rows(rows, "analyst_email").items()
    ]
    analysts.sort(key=lambda a: (-a.questions, -a.cost_usd, a.email))

    labels = {row.theme_key: row.theme_label for row in rows}
    themes = [
        ThemeRow(
            key=key,
            label=labels[key],
            questions=questions,
            conversations=convs,
            cost_usd=_money(cost),
            share=round(questions / total_questions, 4) if total_questions else 0.0,
        )
        for key, (convs, questions, cost) in _group_rows(rows, "theme_key").items()
    ]
    themes.sort(key=lambda t: (t.key == OTHER_THEME_KEY, -t.questions, -t.conversations, t.label))

    per_ws = _group_rows(rows, "workspace_slug")
    ws_rows = []
    for ws in workspaces:
        convs, questions, cost = per_ws.get(ws.slug, (0, 0, 0.0))
        ws_rows.append(
            WorkspaceRow(
                id=ws.id,
                slug=ws.slug,
                name=ws.name,
                questions=questions,
                conversations=convs,
                cost_usd=_money(cost),
            )
        )

    totals = ReportTotals(
        questions=total_questions,
        conversations=len(rows),
        analysts=len(analysts),
        messages=sum(row.messages for row in rows),
        cost_usd=_money(total_cost),
        avg_cost_per_question=_avg(total_cost, total_questions),
        avg_cost_per_conversation=_avg(total_cost, len(rows)),
        avg_cost_per_analyst=_avg(total_cost, len(analysts)),
    )
    return WorkspaceReport(
        totals=totals,
        analysts=analysts,
        weeks=_weeks(grouped, start, end, tz),
        themes=themes,
        workspaces=ws_rows,
        conversations=rows,
    )
