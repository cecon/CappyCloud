"""SQLAlchemy adapter for user repository workspaces."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import UserRepositoryWorkspace as UserRepositoryWorkspaceEntity
from app.domain.value_objects import validate_user_workspace_status
from app.infrastructure.orm_models_user_workspaces import (
    UserRepositoryWorkspace as UserRepositoryWorkspaceORM,
)
from app.ports.user_workspaces import UserRepositoryWorkspaceRepository


class SQLAlchemyUserRepositoryWorkspaceRepository(UserRepositoryWorkspaceRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, workspace_id: uuid.UUID) -> UserRepositoryWorkspaceEntity | None:
        row = await self._session.get(UserRepositoryWorkspaceORM, workspace_id)
        return self._to_entity(row) if row else None

    async def get_for_scope(
        self,
        *,
        user_id: uuid.UUID,
        repository_id: uuid.UUID,
        sandbox_key: str,
        base_branch: str,
    ) -> UserRepositoryWorkspaceEntity | None:
        result = await self._session.execute(
            select(UserRepositoryWorkspaceORM)
            .where(UserRepositoryWorkspaceORM.user_id == user_id)
            .where(UserRepositoryWorkspaceORM.repository_id == repository_id)
            .where(UserRepositoryWorkspaceORM.sandbox_key == sandbox_key)
            .where(UserRepositoryWorkspaceORM.base_branch == base_branch)
        )
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def list_for_user(self, user_id: uuid.UUID) -> list[UserRepositoryWorkspaceEntity]:
        result = await self._session.execute(
            select(UserRepositoryWorkspaceORM)
            .where(UserRepositoryWorkspaceORM.user_id == user_id)
            .order_by(UserRepositoryWorkspaceORM.updated_at.desc())
        )
        return [self._to_entity(row) for row in result.scalars().all()]

    async def save(self, workspace: UserRepositoryWorkspaceEntity) -> UserRepositoryWorkspaceEntity:
        row = await self._session.get(UserRepositoryWorkspaceORM, workspace.id)
        status = validate_user_workspace_status(workspace.status)
        if row is None:
            row = UserRepositoryWorkspaceORM(
                id=workspace.id,
                user_id=workspace.user_id,
                repository_id=workspace.repository_id,
                sandbox_id=workspace.sandbox_id,
                sandbox_key=workspace.sandbox_key,
                base_branch=workspace.base_branch,
                workspace_path=workspace.workspace_path,
                status=status,
                health_message=workspace.health_message,
                last_prepared_at=workspace.last_prepared_at,
                last_used_at=workspace.last_used_at,
            )
            self._session.add(row)
        else:
            row.sandbox_id = workspace.sandbox_id
            row.sandbox_key = workspace.sandbox_key
            row.base_branch = workspace.base_branch
            row.workspace_path = workspace.workspace_path
            row.status = status
            row.health_message = workspace.health_message
            row.last_prepared_at = workspace.last_prepared_at
            row.last_used_at = workspace.last_used_at
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_entity(row)

    async def delete(self, workspace_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        row = await self._session.get(UserRepositoryWorkspaceORM, workspace_id)
        if row is None or row.user_id != user_id:
            return False
        await self._session.delete(row)
        await self._session.commit()
        return True

    @staticmethod
    def _to_entity(row: UserRepositoryWorkspaceORM) -> UserRepositoryWorkspaceEntity:
        return UserRepositoryWorkspaceEntity(
            id=row.id,
            user_id=row.user_id,
            repository_id=row.repository_id,
            sandbox_id=row.sandbox_id,
            sandbox_key=row.sandbox_key,
            base_branch=row.base_branch,
            workspace_path=row.workspace_path,
            status=validate_user_workspace_status(row.status),
            health_message=row.health_message,
            last_prepared_at=row.last_prepared_at,
            last_used_at=row.last_used_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
