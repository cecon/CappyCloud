"""Exporta as conversas de um workspace com o número do chamado (CSV, só admin).

Serve para cruzar o que a Cappy resolveu com os chamados do Zendesk:
uma linha por conversa, com usuário, datas, uso, custo e PR.
"""

from __future__ import annotations

import codecs
import csv
import io
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import get_db_session
from app.adapters.primary.http.deps_auth import require_role
from app.domain.entities import UserRole
from app.infrastructure.orm_models import Conversation, Message, User
from app.infrastructure.orm_models_workspaces import Workspace

router = APIRouter(
    prefix="/admin/workspaces",
    tags=["admin"],
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)

COLUMNS = [
    "chamado",
    "workspace",
    "usuario",
    "titulo",
    "criada_em",
    "ultima_atividade",
    "perguntas",
    "tokens_entrada",
    "tokens_saida",
    "custo_usd",
    "arquivos_alterados",
    "linhas_adicionadas",
    "linhas_removidas",
    "pr_url",
    "pr_status",
    "arquivada",
]


def _iso(value) -> str:
    return value.isoformat(timespec="seconds") if value else ""


@router.get("/{workspace_id}/tickets.csv")
async def export_workspace_tickets(
    workspace_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    ws = await session.get(Workspace, workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace não encontrado.")
    usage = (
        select(
            Message.conversation_id.label("cid"),
            func.sum(case((Message.role == "user", 1), else_=0)).label("questions"),
            func.sum(Message.prompt_tokens).label("prompt_tokens"),
            func.sum(Message.completion_tokens).label("completion_tokens"),
            func.sum(Message.cost_usd).label("cost_usd"),
            func.max(Message.created_at).label("last_at"),
        )
        .group_by(Message.conversation_id)
        .subquery()
    )
    rows = (
        await session.execute(
            select(Conversation, User.email, usage)
            .join(User, User.id == Conversation.user_id)
            .outerjoin(usage, usage.c.cid == Conversation.id)
            .where(Conversation.workspace_id == workspace_id)
            .order_by(Conversation.created_at)
        )
    ).all()

    buffer = io.StringIO()
    # Ponto e vírgula: o Excel em português abre direto em colunas.
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(COLUMNS)
    for row in rows:
        conv: Conversation = row[0]
        writer.writerow(
            [
                conv.ticket_number or "",
                ws.slug,
                row.email,
                conv.title,
                _iso(conv.created_at),
                _iso(row.last_at or conv.updated_at),
                int(row.questions or 0),
                int(row.prompt_tokens or 0),
                int(row.completion_tokens or 0),
                f"{float(row.cost_usd or 0):.4f}",
                conv.files_changed,
                conv.lines_added,
                conv.lines_removed,
                conv.pr_url or "",
                conv.pr_status,
                "sim" if conv.archived_at else "nao",
            ]
        )
    return Response(
        # BOM para o Excel reconhecer UTF-8 (acentos dos títulos).
        content=codecs.BOM_UTF8 + buffer.getvalue().encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="chamados-{ws.slug}.csv"'},
    )
