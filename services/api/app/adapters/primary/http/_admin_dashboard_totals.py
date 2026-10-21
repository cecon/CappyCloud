"""Totais do dashboard admin: globais (ADMIN) ou restritos aos workspaces do escopo."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.domain.entities import UserRole
from app.infrastructure.orm_models import Conversation, Message, Sandbox
from app.infrastructure.orm_models import User as UserORM
from app.infrastructure.orm_models_execution import AgentTask
from app.infrastructure.orm_models_workspaces import UserWorkspaceAccess, Workspace


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


def as_int(value: Any) -> int:
    return int(value or 0)


def as_float(value: Any) -> float:
    if isinstance(value, Decimal):
        return float(value)
    return float(value or 0)


async def _scalar_int(session: AsyncSession, stmt: Any) -> int:
    value = await session.scalar(stmt)
    return as_int(value)


def in_workspace(stmt: Select[Any], workspace_ids: list[uuid.UUID] | None) -> Select[Any]:
    """Restringe uma consulta sobre ``Message`` às conversas dos workspaces."""
    if workspace_ids is None:
        return stmt
    return stmt.join(Conversation, Conversation.id == Message.conversation_id).where(
        Conversation.workspace_id.in_(workspace_ids)
    )


def conversations_in(stmt: Select[Any], workspace_ids: list[uuid.UUID] | None) -> Select[Any]:
    if workspace_ids is None:
        return stmt
    return stmt.where(Conversation.workspace_id.in_(workspace_ids))


async def _scoped_totals(
    session: AsyncSession, cutoff_24h: datetime, workspace_ids: list[uuid.UUID], usage: Any
) -> AdminDashboardTotals:
    """Admin de workspace: todo contador fica restrito aos workspaces dele."""
    in_scope = UserWorkspaceAccess.workspace_id.in_(workspace_ids)
    conversations = select(Conversation.id).where(Conversation.workspace_id.in_(workspace_ids))
    sandbox_ids = select(Workspace.sandbox_id).where(Workspace.id.in_(workspace_ids))
    return AdminDashboardTotals(
        users=await _scalar_int(
            session, select(func.count(func.distinct(UserWorkspaceAccess.user_id))).where(in_scope)
        ),
        admins=await _scalar_int(
            session,
            select(func.count(func.distinct(UserWorkspaceAccess.user_id))).where(
                in_scope, UserWorkspaceAccess.is_admin.is_(True)
            ),
        ),
        conversations=await _scalar_int(
            session, conversations_in(select(func.count(Conversation.id)), workspace_ids)
        ),
        conversations_24h=await _scalar_int(
            session,
            conversations_in(
                select(func.count(Conversation.id)).where(Conversation.created_at >= cutoff_24h),
                workspace_ids,
            ),
        ),
        messages=await _scalar_int(
            session, in_workspace(select(func.count(Message.id)), workspace_ids)
        ),
        assistant_messages=await _scalar_int(
            session,
            in_workspace(
                select(func.count(Message.id)).where(Message.role == "assistant"), workspace_ids
            ),
        ),
        running_tasks=await _scalar_int(
            session,
            select(func.count(AgentTask.id)).where(
                AgentTask.status.in_(("pending", "running", "paused")),
                AgentTask.conversation_id.in_(conversations),
            ),
        ),
        failed_tasks_24h=await _scalar_int(
            session,
            select(func.count(AgentTask.id)).where(
                AgentTask.status == "error",
                AgentTask.created_at >= cutoff_24h,
                AgentTask.conversation_id.in_(conversations),
            ),
        ),
        open_pull_requests=await _scalar_int(
            session,
            conversations_in(
                select(func.count(Conversation.id)).where(
                    Conversation.pr_status.in_(("open", "draft"))
                ),
                workspace_ids,
            ),
        ),
        sandboxes=await _scalar_int(
            session, select(func.count(Sandbox.id)).where(Sandbox.id.in_(sandbox_ids))
        ),
        active_sandboxes=await _scalar_int(
            session,
            select(func.count(Sandbox.id)).where(
                Sandbox.id.in_(sandbox_ids),
                or_(
                    Sandbox.status == "active",
                    Sandbox.container_status.in_(("running", "configuring", "configured")),
                ),
            ),
        ),
        prompt_tokens=as_int(usage[0]),
        completion_tokens=as_int(usage[1]),
        total_cost_usd=as_float(usage[2]),
    )


async def dashboard_totals(
    session: AsyncSession,
    cutoff_24h: datetime,
    workspace_id: list[uuid.UUID] | None,
    *,
    scoped_counters: bool = False,
) -> AdminDashboardTotals:
    usage_stmt = select(
        func.coalesce(func.sum(Message.prompt_tokens), 0),
        func.coalesce(func.sum(Message.completion_tokens), 0),
        func.coalesce(func.sum(Message.cost_usd), 0),
    )
    usage = (await session.execute(in_workspace(usage_stmt, workspace_id))).one()
    if scoped_counters and workspace_id is not None:
        return await _scoped_totals(session, cutoff_24h, workspace_id, usage)

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
        prompt_tokens=as_int(usage[0]),
        completion_tokens=as_int(usage[1]),
        total_cost_usd=as_float(usage[2]),
    )
