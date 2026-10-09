"""SQLAlchemy: dados crus do relatório de uso por workspace."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.orm_models import Conversation, Message
from app.infrastructure.orm_models import User as UserORM
from app.infrastructure.orm_models_workspaces import UserWorkspaceAccess, Workspace
from app.ports.workspace_report import (
    ReportConversation,
    ReportMessage,
    ReportWorkspace,
    WorkspaceReportRepository,
    branches_from_repos,
)

# A primeira mensagem só serve para achar o tema; não precisa vir inteira.
FIRST_MESSAGE_MAX_CHARS = 2000


def _utc(value: datetime) -> datetime:
    """SQLite devolve datas sem fuso; no banco elas já estão em UTC."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _to_workspace(ws: Workspace) -> ReportWorkspace:
    return ReportWorkspace(
        id=ws.id,
        slug=ws.slug,
        name=ws.name,
        theme_preset=ws.report_theme_preset,
        theme_rules=ws.report_themes,
    )


def _as_float(value: Any) -> float:
    if isinstance(value, Decimal):
        return float(value)
    return float(value or 0)


class SQLAlchemyWorkspaceReportRepository(WorkspaceReportRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_workspaces(self) -> list[ReportWorkspace]:
        rows = await self._session.execute(select(Workspace).order_by(Workspace.name))
        return [_to_workspace(ws) for ws in rows.scalars()]

    async def accessible_workspace_ids(self, user_id: uuid.UUID) -> set[uuid.UUID]:
        rows = await self._session.execute(
            select(UserWorkspaceAccess.workspace_id).where(UserWorkspaceAccess.user_id == user_id)
        )
        return set(rows.scalars())

    async def list_period_messages(
        self, workspace_ids: Sequence[uuid.UUID], start: datetime, end: datetime
    ) -> list[ReportMessage]:
        if not workspace_ids:
            return []
        rows = await self._session.execute(
            select(Message.conversation_id, Message.created_at, Message.cost_usd, Message.role)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(
                Conversation.workspace_id.in_(list(workspace_ids)),
                Message.created_at >= start,
                Message.created_at < end,
            )
        )
        return [
            ReportMessage(
                conversation_id=row.conversation_id,
                created_at=_utc(row.created_at),
                cost_usd=_as_float(row.cost_usd),
                is_question=row.role == "user",
            )
            for row in rows
        ]

    async def _first_user_messages(self, ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
        ranked = (
            select(
                Message.conversation_id,
                Message.content,
                func.row_number()
                .over(partition_by=Message.conversation_id, order_by=Message.created_at)
                .label("rn"),
            )
            .where(Message.conversation_id.in_(ids), Message.role == "user")
            .subquery()
        )
        rows = await self._session.execute(
            select(ranked.c.conversation_id, ranked.c.content).where(ranked.c.rn == 1)
        )
        return {row.conversation_id: (row.content or "")[:FIRST_MESSAGE_MAX_CHARS] for row in rows}

    async def get_conversations(
        self, conversation_ids: Sequence[uuid.UUID]
    ) -> list[ReportConversation]:
        ids = list(conversation_ids)
        if not ids:
            return []
        rows = (
            await self._session.execute(
                select(
                    Conversation.id,
                    Conversation.workspace_id,
                    Conversation.title,
                    Conversation.ticket_number,
                    Conversation.repos,
                    UserORM.email,
                )
                .join(UserORM, UserORM.id == Conversation.user_id)
                .where(Conversation.id.in_(ids), Conversation.workspace_id.is_not(None))
            )
        ).all()
        first = await self._first_user_messages(ids)
        return [
            ReportConversation(
                id=row.id,
                workspace_id=row.workspace_id,
                user_email=row.email,
                title=row.title,
                ticket_number=row.ticket_number,
                branches=branches_from_repos(row.repos),
                first_user_message=first.get(row.id, ""),
            )
            for row in rows
        ]

    async def list_branches(self, workspace_ids: Sequence[uuid.UUID]) -> list[str]:
        if not workspace_ids:
            return []
        rows = await self._session.execute(
            select(Conversation.repos).where(Conversation.workspace_id.in_(list(workspace_ids)))
        )
        found: set[str] = set()
        for repos in rows.scalars():
            found |= branches_from_repos(repos)
        return sorted(found)

    async def save_theme_config(
        self,
        workspace_id: uuid.UUID,
        preset: str | None,
        rules: list[dict[str, Any]] | None,
    ) -> ReportWorkspace | None:
        ws = await self._session.get(Workspace, workspace_id)
        if ws is None:
            return None
        ws.report_theme_preset = preset
        ws.report_themes = rules
        await self._session.commit()
        await self._session.refresh(ws)
        return _to_workspace(ws)
