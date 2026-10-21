"""Admin: listar e ler qualquer conversa (só leitura).

  GET /admin/conversations?q=&workspace_id=&limit=&offset=   → lista com usuário, workspace e uso
  GET /admin/conversations/{id}                             → conversa completa com as mensagens

``q`` procura no título, no e-mail do usuário e no número do chamado.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import case, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import get_db_session, require_role
from app.domain.entities import UserRole
from app.infrastructure.orm_models import Conversation, Message
from app.infrastructure.orm_models import User as UserORM
from app.infrastructure.orm_models_workspaces import Workspace

router = APIRouter(
    prefix="/admin/conversations",
    tags=["admin"],
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)

Session = Annotated[AsyncSession, Depends(get_db_session)]


class AdminConversationItem(BaseModel):
    id: uuid.UUID
    title: str
    user_email: str | None
    workspace_slug: str | None
    workspace_name: str | None
    ticket_number: str | None
    created_at: datetime
    last_message_at: datetime | None
    questions: int
    message_count: int
    cost_usd: float
    pr_url: str | None
    archived: bool


class AdminConversationPage(BaseModel):
    total: int
    items: list[AdminConversationItem]


class AdminConversationMessage(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime
    model_used: str | None
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


class AdminConversationDetail(AdminConversationItem):
    messages: list[AdminConversationMessage]


def _usage():
    return (
        select(
            Message.conversation_id.label("cid"),
            func.count(Message.id).label("messages"),
            func.sum(case((Message.role == "user", 1), else_=0)).label("questions"),
            func.sum(Message.cost_usd).label("cost"),
            func.max(Message.created_at).label("last_at"),
        )
        .group_by(Message.conversation_id)
        .subquery()
    )


def _query(usage):
    return (
        select(Conversation, UserORM.email, Workspace.slug, Workspace.name, usage)
        .join(UserORM, UserORM.id == Conversation.user_id)
        .outerjoin(Workspace, Workspace.id == Conversation.workspace_id)
        .outerjoin(usage, usage.c.cid == Conversation.id)
    )


def _item(row) -> dict:
    conv: Conversation = row[0]
    return {
        "id": conv.id,
        "title": conv.title,
        "user_email": row.email,
        "workspace_slug": row.slug,
        "workspace_name": row.name,
        "ticket_number": conv.ticket_number,
        "created_at": conv.created_at,
        "last_message_at": row.last_at,
        "questions": int(row.questions or 0),
        "message_count": int(row.messages or 0),
        "cost_usd": float(row.cost or 0),
        "pr_url": conv.pr_url,
        "archived": conv.archived_at is not None,
    }


@router.get("", response_model=AdminConversationPage)
async def list_conversations(
    session: Session,
    q: str = Query(default="", max_length=200),
    workspace_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AdminConversationPage:
    usage = _usage()
    query = _query(usage)
    term = q.strip().lstrip("#")
    if term:
        pattern = f"%{term}%"
        query = query.where(
            or_(
                Conversation.title.ilike(pattern),
                UserORM.email.ilike(pattern),
                Conversation.ticket_number.ilike(pattern),
            )
        )
    if workspace_id:
        query = query.where(Conversation.workspace_id == workspace_id)
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    rows = (
        await session.execute(
            query.order_by(desc(func.coalesce(usage.c.last_at, Conversation.created_at)))
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return AdminConversationPage(
        total=int(total or 0), items=[AdminConversationItem(**_item(row)) for row in rows]
    )


@router.get("/{conversation_id}", response_model=AdminConversationDetail)
async def get_conversation(conversation_id: uuid.UUID, session: Session) -> AdminConversationDetail:
    usage = _usage()
    row = (await session.execute(_query(usage).where(Conversation.id == conversation_id))).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Conversa não encontrada.")
    messages = (
        await session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
    ).scalars()
    return AdminConversationDetail(
        **_item(row),
        messages=[
            AdminConversationMessage(
                id=m.id,
                role=m.role,
                content=m.content,
                created_at=m.created_at,
                model_used=m.model_used,
                prompt_tokens=m.prompt_tokens,
                completion_tokens=m.completion_tokens,
                cost_usd=float(m.cost_usd or 0),
            )
            for m in messages
        ],
    )
