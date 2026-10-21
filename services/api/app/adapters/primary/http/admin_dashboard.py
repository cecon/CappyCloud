"""HTTP adapter for the administrative operational dashboard."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import case, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.adapters.primary.http.deps import get_db_session, require_role
from app.domain.entities import User, UserRole
from app.infrastructure.orm_models import Conversation, Message, Sandbox
from app.infrastructure.orm_models import User as UserORM
from app.infrastructure.orm_models_execution import AgentTask

router = APIRouter(prefix="/admin/dashboard", tags=["admin"])

COST_PERIOD_DAYS = (7, 15, 30)


class AdminDashboardTotals(BaseModel):
    users: int
    admins: int
    conversations: int
    conversations_24h: int
    messages: int
    assistant_messages: int
    running_tasks: int
    failed_tasks_24h: int
    open_pull_requests: int
    sandboxes: int
    active_sandboxes: int
    prompt_tokens: int
    completion_tokens: int
    total_cost_usd: float


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


def _as_int(value: Any) -> int:
    return int(value or 0)


def _as_float(value: Any) -> float:
    if isinstance(value, Decimal):
        return float(value)
    return float(value or 0)


def _preview(content: str | None, max_len: int = 180) -> str | None:
    if not content:
        return None
    text = " ".join(content.split())
    if not text:
        return None
    return text[: max_len - 1] + "..." if len(text) > max_len else text


async def _scalar_int(session: AsyncSession, stmt: Any) -> int:
    value = await session.scalar(stmt)
    return _as_int(value)


def _in_workspace(stmt: Select[Any], workspace_id: uuid.UUID | None) -> Select[Any]:
    """Restringe uma consulta sobre ``Message`` às conversas do workspace."""
    if workspace_id is None:
        return stmt
    return stmt.join(Conversation, Conversation.id == Message.conversation_id).where(
        Conversation.workspace_id == workspace_id
    )


async def _cost_periods(
    session: AsyncSession, now: datetime, workspace_id: uuid.UUID | None
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
    row = (await session.execute(_in_workspace(stmt, workspace_id))).one()
    return [
        AdminDashboardCostPeriod(
            days=days,
            cost_usd=_as_float(row[idx * 4]),
            prompt_tokens=_as_int(row[idx * 4 + 1]),
            completion_tokens=_as_int(row[idx * 4 + 2]),
            conversations=_as_int(row[idx * 4 + 3]),
        )
        for idx, days in enumerate(COST_PERIOD_DAYS)
    ]


async def _dashboard_totals(
    session: AsyncSession, cutoff_24h: datetime, workspace_id: uuid.UUID | None
) -> AdminDashboardTotals:
    usage_stmt = select(
        func.coalesce(func.sum(Message.prompt_tokens), 0),
        func.coalesce(func.sum(Message.completion_tokens), 0),
        func.coalesce(func.sum(Message.cost_usd), 0),
    )
    usage = (await session.execute(_in_workspace(usage_stmt, workspace_id))).one()

    return AdminDashboardTotals(
        users=await _scalar_int(session, select(func.count(UserORM.id))),
        admins=await _scalar_int(
            session, select(func.count(UserORM.id)).where(UserORM.role == UserRole.ADMIN.value)
        ),
        conversations=await _scalar_int(session, select(func.count(Conversation.id))),
        conversations_24h=await _scalar_int(
            session,
            select(func.count(Conversation.id)).where(Conversation.created_at >= cutoff_24h),
        ),
        messages=await _scalar_int(session, select(func.count(Message.id))),
        assistant_messages=await _scalar_int(
            session, select(func.count(Message.id)).where(Message.role == "assistant")
        ),
        running_tasks=await _scalar_int(
            session,
            select(func.count(AgentTask.id)).where(
                AgentTask.status.in_(("pending", "running", "paused"))
            ),
        ),
        failed_tasks_24h=await _scalar_int(
            session,
            select(func.count(AgentTask.id)).where(
                AgentTask.status == "error", AgentTask.created_at >= cutoff_24h
            ),
        ),
        open_pull_requests=await _scalar_int(
            session,
            select(func.count(Conversation.id)).where(
                Conversation.pr_status.in_(("open", "draft"))
            ),
        ),
        sandboxes=await _scalar_int(session, select(func.count(Sandbox.id))),
        active_sandboxes=await _scalar_int(
            session,
            select(func.count(Sandbox.id)).where(
                or_(
                    Sandbox.status == "active",
                    Sandbox.container_status.in_(("running", "configuring", "configured")),
                )
            ),
        ),
        prompt_tokens=_as_int(usage[0]),
        completion_tokens=_as_int(usage[1]),
        total_cost_usd=_as_float(usage[2]),
    )


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
    session: AsyncSession, limit: int, workspace_id: uuid.UUID | None
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
    if workspace_id is not None:
        stmt = stmt.where(Conversation.workspace_id == workspace_id)
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
            message_count=_as_int(row.message_count),
            cost_usd=_as_float(row.cost_usd),
            ci_status=row.ci_status,
            pr_status=row.pr_status,
        )
        for row in rows
    ]


@router.get("", response_model=AdminDashboardOut)
async def get_admin_dashboard(
    _admin: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(default=12, ge=1, le=50),
    workspace_id: uuid.UUID | None = None,
) -> AdminDashboardOut:
    """Return high-level operational metrics for administrators.

    Com ``workspace_id``, tokens, custo (total e por período) e as últimas
    conversas ficam restritos ao workspace; os contadores operacionais
    (usuários, sandboxes, execuções) continuam globais.
    """
    now = datetime.now(UTC)
    cutoff_24h = now - timedelta(hours=24)
    return AdminDashboardOut(
        generated_at=now,
        workspace_id=workspace_id,
        totals=await _dashboard_totals(session, cutoff_24h, workspace_id),
        cost_periods=await _cost_periods(session, now, workspace_id),
        recent_conversations=await _recent_conversations(session, limit, workspace_id),
    )
