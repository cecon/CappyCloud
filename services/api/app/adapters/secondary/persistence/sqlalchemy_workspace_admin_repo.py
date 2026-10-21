"""Adapter SQLAlchemy da leitura de acessos usada pelo escopo de admin."""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.orm_models_access import UserAiModelAccess
from app.infrastructure.orm_models_workspaces import UserWorkspaceAccess
from app.ports.workspace_admin import WorkspaceAdminRepository


class SQLAlchemyWorkspaceAdminRepository(WorkspaceAdminRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def admin_workspace_ids(self, user_id: uuid.UUID) -> set[uuid.UUID]:
        rows = await self._session.execute(
            select(UserWorkspaceAccess.workspace_id).where(
                UserWorkspaceAccess.user_id == user_id, UserWorkspaceAccess.is_admin.is_(True)
            )
        )
        return set(rows.scalars())

    async def member_workspace_ids(self, user_id: uuid.UUID) -> set[uuid.UUID]:
        rows = await self._session.execute(
            select(UserWorkspaceAccess.workspace_id).where(UserWorkspaceAccess.user_id == user_id)
        )
        return set(rows.scalars())

    async def member_user_ids(self, workspace_ids: Iterable[uuid.UUID]) -> set[uuid.UUID]:
        ids = list(workspace_ids)
        if not ids:
            return set()
        rows = await self._session.execute(
            select(UserWorkspaceAccess.user_id).where(UserWorkspaceAccess.workspace_id.in_(ids))
        )
        return set(rows.scalars())

    async def grant_access(self, user_id: uuid.UUID, workspace_id: uuid.UUID) -> None:
        exists = await self._session.execute(
            select(UserWorkspaceAccess.id).where(
                UserWorkspaceAccess.user_id == user_id,
                UserWorkspaceAccess.workspace_id == workspace_id,
            )
        )
        if exists.scalar_one_or_none() is not None:
            return
        self._session.add(
            UserWorkspaceAccess(id=uuid.uuid4(), user_id=user_id, workspace_id=workspace_id)
        )
        await self._session.commit()

    async def copy_model_access(self, from_user_id: uuid.UUID, to_user_id: uuid.UUID) -> None:
        source = set(
            (
                await self._session.execute(
                    select(UserAiModelAccess.ai_model_id).where(
                        UserAiModelAccess.user_id == from_user_id
                    )
                )
            ).scalars()
        )
        current = set(
            (
                await self._session.execute(
                    select(UserAiModelAccess.ai_model_id).where(
                        UserAiModelAccess.user_id == to_user_id
                    )
                )
            ).scalars()
        )
        for model_id in source - current:
            self._session.add(
                UserAiModelAccess(id=uuid.uuid4(), user_id=to_user_id, ai_model_id=model_id)
            )
        await self._session.commit()
