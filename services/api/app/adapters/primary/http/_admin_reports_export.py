"""Arquivos do relatório de uso: XLSX (abas para a Diretoria) e CSV (conversas)."""

from __future__ import annotations

import codecs
import csv
import io
from collections.abc import Sequence
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.worksheet.worksheet import Worksheet

from app.application.use_cases.workspace_report import BuiltReport

USD_FORMAT = '"US$" #,##0.0000'
BRL_FORMAT = '"R$" #,##0.00'
COST_SOURCE = (
    "Custo em US$ somado de messages.cost_usd: preço da tabela oficial da API da Claude "
    "por modelo e tipo de token (entrada, cache e saída), calculado pelo runtime a cada turno."
)

CONVERSATION_COLUMNS = [
    "workspace",
    "analista",
    "chamado",
    "titulo",
    "tema",
    "branches",
    "perguntas_no_periodo",
    "mensagens_no_periodo",
    "custo_usd",
    "custo_brl",
    "primeira_mensagem",
    "ultima_mensagem",
]


def export_filename(built: BuiltReport, ext: str) -> str:
    return f"relatorio-{built.scope_slug}-{built.start.isoformat()}-{built.end.isoformat()}.{ext}"


def _local(value: datetime) -> datetime:
    """openpyxl não grava fuso; a data já está no fuso do relatório."""
    return value.replace(tzinfo=None)


def _brl(built: BuiltReport, usd: float) -> float | None:
    return round(usd * built.brl.rate, 2) if built.brl else None


def rate_note(built: BuiltReport) -> str:
    if built.brl is None:
        return "Sem cotação: a fonte do câmbio não respondeu; valores só em US$."
    quoted = built.brl.quoted_on.strftime("%d/%m/%Y")
    return f"R$ {built.brl.rate:.4f} por US$ ({built.brl.source}, {quoted})."


def _conversation_values(built: BuiltReport) -> list[list[Any]]:
    return [
        [
            row.workspace_slug,
            row.analyst_email,
            row.ticket_number or "",
            row.title,
            row.theme_label,
            ", ".join(row.branches),
            row.questions,
            row.messages,
            row.cost_usd,
            _brl(built, row.cost_usd),
            _local(row.first_message_at),
            _local(row.last_message_at),
        ]
        for row in built.report.conversations
    ]


def report_csv(built: BuiltReport) -> bytes:
    buffer = io.StringIO()
    # Ponto e vírgula: o Excel em português abre direto em colunas.
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(CONVERSATION_COLUMNS)
    for values in _conversation_values(built):
        values[8] = f"{values[8]:.6f}"
        values[9] = "" if values[9] is None else f"{values[9]:.2f}"
        values[10] = values[10].isoformat(timespec="seconds")
        values[11] = values[11].isoformat(timespec="seconds")
        writer.writerow(values)
    # BOM para o Excel reconhecer UTF-8 (acentos dos títulos).
    return codecs.BOM_UTF8 + buffer.getvalue().encode("utf-8")


def _sheet(
    wb: Workbook,
    title: str,
    header: Sequence[str],
    rows: Sequence[Sequence[Any]],
    formats: dict[int, str] | None = None,
) -> Worksheet:
    ws = wb.create_sheet(title)
    ws.append(list(header))
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for values in rows:
        ws.append(list(values))
    for col, number_format in (formats or {}).items():
        for (cell,) in ws.iter_rows(min_row=2, min_col=col, max_col=col):
            cell.number_format = number_format
    for idx, name in enumerate(header, start=1):
        ws.column_dimensions[ws.cell(row=1, column=idx).column_letter].width = max(
            14, min(60, len(name) + 4)
        )
    return ws


def _summary_rows(built: BuiltReport) -> list[tuple[str, Any, str | None]]:
    t = built.report.totals
    generated = built.generated_at.astimezone(ZoneInfo(built.timezone))
    return [
        ("Workspace", built.workspace_name or "Todos os workspaces visíveis", None),
        ("Branch", built.branch or "Todas", None),
        ("Período", f"{built.start:%d/%m/%Y} a {built.end:%d/%m/%Y} ({built.timezone})", None),
        ("Gerado em", _local(generated), None),
        ("Total de consultas (perguntas)", t.questions, None),
        ("Conversas", t.conversations, None),
        ("Analistas", t.analysts, None),
        ("Custo total (US$)", t.cost_usd, USD_FORMAT),
        ("Custo total (R$)", _brl(built, t.cost_usd), BRL_FORMAT),
        ("Custo médio por consulta (US$)", t.avg_cost_per_question, USD_FORMAT),
        ("Custo médio por consulta (R$)", _brl(built, t.avg_cost_per_question), BRL_FORMAT),
        ("Custo médio por analista (US$)", t.avg_cost_per_analyst, USD_FORMAT),
        ("Cotação", rate_note(built), None),
        ("Fonte do custo", COST_SOURCE, None),
    ]


def report_xlsx(built: BuiltReport) -> bytes:
    report = built.report
    wb = Workbook()
    wb.remove(wb.active)
    rows = _summary_rows(built)
    summary = _sheet(wb, "Resumo", ["Indicador", "Valor"], [r[:2] for r in rows])
    for idx, (_label, _value, number_format) in enumerate(rows, start=2):
        if number_format:
            summary.cell(row=idx, column=2).number_format = number_format
    summary.column_dimensions["A"].width = 34
    summary.column_dimensions["B"].width = 70
    money = {4: USD_FORMAT, 5: BRL_FORMAT}
    _sheet(
        wb,
        "Analistas",
        ["Analista", "E-mail", "Consultas", "Custo (US$)", "Custo (R$)", "Conversas"],
        [
            [a.label, a.email, a.questions, a.cost_usd, _brl(built, a.cost_usd), a.conversations]
            for a in report.analysts
        ],
        money,
    )
    _sheet(
        wb,
        "Semanas",
        ["Semana", "Início", "Consultas", "Custo (US$)", "Custo (R$)", "Fim"],
        [
            [w.label, w.start, w.questions, w.cost_usd, _brl(built, w.cost_usd), w.end]
            for w in report.weeks
        ],
        money,
    )
    _sheet(
        wb,
        "Temas",
        ["Tema", "Participação", "Consultas", "Custo (US$)", "Custo (R$)", "Conversas"],
        [
            [t.label, t.share, t.questions, t.cost_usd, _brl(built, t.cost_usd), t.conversations]
            for t in report.themes
        ],
        {2: "0%", **money},
    )
    if built.workspace_id is None:
        _sheet(
            wb,
            "Workspaces",
            ["Workspace", "Slug", "Consultas", "Custo (US$)", "Custo (R$)", "Conversas"],
            [
                [w.name, w.slug, w.questions, w.cost_usd, _brl(built, w.cost_usd), w.conversations]
                for w in report.workspaces
            ],
            money,
        )
    _sheet(
        wb,
        "Conversas",
        CONVERSATION_COLUMNS,
        _conversation_values(built),
        {9: USD_FORMAT, 10: BRL_FORMAT},
    )
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
