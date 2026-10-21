"""HTTP adapter for the administrative operational dashboard."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http._admin_dashboard_totals import (
    AdminDashboardTotals,
    as_float,
    as_int,
    conversations_in,
    dashboard_totals,
    in_workspace,
)
from app.adapters.primary.http.deps import get_db_session
from app.adapters.primary.http.deps_auth import get_admin_scope
from app.application.use_cases.admin_scope import AdminScope
from app.infrastructure.orm_models import Conversation, Message
from app.infrastructure.orm_models import User as UserORM

router = APIRouter(prefix="/admin/dashboard", tags=["admin"])

COST_PERIOD_DAYS = (7, 15, 30)


class AdminDashboardConversation(BaseModel):
    id: uuid.UUID
    title: str
    user_id: uuid.UUID
    user_email: str | None
    sandbox_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None
    last_message_preview: str | None
    model_used: str | None
    message_count: int
    cost_usd: float
    ci_status: str
    pr_status: str


class AdminDashboardCostPeriod(BaseModel):
    days: int
    cost_usd: float
    prompt_tokens: int
    completion_tokens: int
    conversations: int


class AdminDashboardOut(BaseModel):
    generated_at: datetime
    workspace_id: uuid.UUID | None = None
    totals: AdminDashboardTotals
    cost_periods: list[AdminDashboardCostPeriod]
    recent_conversations: list[AdminDashboardConversation]


def _preview(content: str | None, max_len: int = 180) -> str | None:
    if not content:
        return None
    text = " ".join(content.split())
    if not text:
        return None
    return text[: max_len - 1] + "..." if len(text) > max_len else text


async def _cost_periods(
    session: AsyncSession, now: datetime, workspace_id: list[uuid.UUID] | None
) -> list[AdminDashboardCostPeriod]:
    """Custo real (``messages.cost_usd``) das janelas de 7, 15 e 30 dias."""
    columns: list[Any] = []
    for days in COST_PERIOD_DAYS:
        recent = Message.created_at >= now - timedelta(days=days)
        columns += [
            func.coalesce(func.sum(case((recent, Message.cost_usd))), 0),
            func.coalesce(func.sum(case((recent, Message.prompt_tokens))), 0),
            func.coalesce(func.sum(case((recent, Message.completion_tokens))), 0),
            func.count(func.distinct(case((recent, Message.conversation_id)))),
        ]
    stmt = select(*columns).where(Message.created_at >= now - timedelta(days=max(COST_PERIOD_DAYS)))
    row = (await session.execute(in_workspace(stmt, workspace_id))).one()
    return [
        AdminDashboardCostPeriod(
            days=days,
            cost_usd=as_float(row[idx * 4]),
            prompt_tokens=as_int(row[idx * 4 + 1]),
            completion_tokens=as_int(row[idx * 4 + 2]),
            conversations=as_int(row[idx * 4 + 3]),
        )
        for idx, days in enumerate(COST_PERIOD_DAYS)
    ]


async def _last_messages(
    session: AsyncSession, conversation_ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[str | None, str | None]]:
    if not conversation_ids:
        return {}
    ranked = (
        select(
            Message.conversation_id,
            Message.content,
            Message.model_used,
            func.row_number()
            .over(partition_by=Message.conversation_id, order_by=desc(Message.created_at))
            .label("rn"),
        )
        .where(Message.conversation_id.in_(conversation_ids))
        .subquery()
    )
    rows = await session.execute(select(ranked).where(ranked.c.rn == 1))
    return {row.conversation_id: (_preview(row.content), row.model_used) for row in rows.fetchall()}


async def _recent_conversations(
    session: AsyncSession, limit: int, workspace_id: list[uuid.UUID] | None
) -> list[AdminDashboardConversation]:
    stmt = (
        select(
            Conversation.id,
            Conversation.title,
            Conversation.user_id,
            UserORM.email.label("user_email"),
            Conversation.sandbox_id,
            Conversation.created_at,
            Conversation.updated_at,
            Conversation.ci_status,
            Conversation.pr_status,
            func.count(Message.id).label("message_count"),
            func.max(Message.created_at).label("last_message_at"),
            func.coalesce(func.sum(Message.cost_usd), 0).label("cost_usd"),
        )
        .join(UserORM, UserORM.id == Conversation.user_id)
        .outerjoin(Message, Message.conversation_id == Conversation.id)
        .group_by(
            Conversation.id,
            Conversation.title,
            Conversation.user_id,
            UserORM.email,
            Conversation.sandbox_id,
            Conversation.created_at,
            Conversation.updated_at,
            Conversation.ci_status,
            Conversation.pr_status,
        )
        .order_by(desc(Conversation.updated_at))
        .limit(limit)
    )
    stmt = conversations_in(stmt, workspace_id)
    rows = (await session.execute(stmt)).fetchall()
    last_by_conversation = await _last_messages(session, [row.id for row in rows])
    return [
        AdminDashboardConversation(
            id=row.id,
            title=row.title,
            user_id=row.user_id,
            user_email=row.user_email,
            sandbox_id=row.sandbox_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
            last_message_at=row.last_message_at,
            last_message_preview=last_by_conversation.get(row.id, (None, None))[0],
            model_used=last_by_conversation.get(row.id, (None, None))[1],
            message_count=as_int(row.message_count),
            cost_usd=as_float(row.cost_usd),
            ci_status=row.ci_status,
            pr_status=row.pr_status,
        )
        for row in rows
    ]


@router.get("", response_model=AdminDashboardOut)
async def get_admin_dashboard(
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(default=12, ge=1, le=50),
    workspace_id: uuid.UUID | None = None,
) -> AdminDashboardOut:
    """Return high-level operational metrics for administrators.

    Com ``workspace_id``, tokens, custo (total e por período) e as últimas
    conversas ficam restritos ao workspace; para ADMIN global os contadores
    operacionais (usuários, sandboxes, execuções) continuam globais. Admin de
    workspace só vê os workspaces que administra, inclusive nos contadores.
    """
    if workspace_id is not None and not scope.allows(workspace_id):
        raise HTTPException(status_code=403, detail="Você não administra este workspace.")
    if workspace_id is not None:
        ws_ids: list[uuid.UUID] | None = [workspace_id]
    elif scope.workspace_ids is not None:
        ws_ids = sorted(scope.workspace_ids)
    else:
        ws_ids = None
    now = datetime.now(UTC)
    cutoff_24h = now - timedelta(hours=24)
    return AdminDashboardOut(
        generated_at=now,
        workspace_id=workspace_id,
        totals=await dashboard_totals(
            session, cutoff_24h, ws_ids, scoped_counters=not scope.is_global
        ),
        cost_periods=await _cost_periods(session, now, ws_ids),
        recent_conversations=await _recent_conversations(session, limit, ws_ids),
    )
