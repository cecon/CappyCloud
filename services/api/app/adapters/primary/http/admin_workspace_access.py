"""Acesso de usuários a workspaces.

  GET    /admin/users/{user_id}/access/workspaces                     → workspaces liberados
  GET    /admin/users/{user_id}/access/workspaces/admin-flags         → onde é admin (super admin)
  POST   /admin/users/{user_id}/access/workspaces/{workspace_id}      → libera
  DELETE /admin/users/{user_id}/access/workspaces/{workspace_id}      → revoga
  PUT    /admin/users/{user_id}/access/workspaces/{workspace_id}/admin → liga/desliga admin

Super admin mexe em tudo. Admin de workspace só nos workspaces que administra e
só em USER comum; promover a admin de workspace é só do super admin.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import get_db_session, get_user_repo
from app.adapters.primary.http.deps_auth import get_workspace_manager_scope, require_super_admin
from app.application.use_cases.admin_scope import (
    AdminScope,
    AdminScopeDeniedError,
    ensure_can_grant,
    ensure_can_revoke,
)
from app.domain.entities import User
from app.infrastructure.orm_models_workspaces import UserWorkspaceAccess
from app.ports.repositories import UserRepository

router = APIRouter(prefix="/admin/users/{user_id}/access/workspaces", tags=["admin"])

Session = Annotated[AsyncSession, Depends(get_db_session)]
# Super admin ou admin de workspace; ADMIN global comum nunca geriu workspaces.
Scope = Annotated[AdminScope, Depends(get_workspace_manager_scope)]
Users = Annotated[UserRepository, Depends(get_user_repo)]


class WorkspaceAdminFlag(BaseModel):
    is_admin: bool


def _forbidden(exc: AdminScopeDeniedError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


async def _target(users: UserRepository, user_id: uuid.UUID) -> User:
    target = await users.get_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    return target


async def _row(
    session: AsyncSession, user_id: uuid.UUID, workspace_id: uuid.UUID
) -> UserWorkspaceAccess | None:
    return (
        await session.execute(
            select(UserWorkspaceAccess).where(
                UserWorkspaceAccess.user_id == user_id,
                UserWorkspaceAccess.workspace_id == workspace_id,
            )
        )
    ).scalar_one_or_none()


@router.get("", response_model=list[uuid.UUID])
async def list_workspace_access(
    user_id: uuid.UUID, session: Session, scope: Scope
) -> list[uuid.UUID]:
    rows = await session.execute(
        select(UserWorkspaceAccess.workspace_id).where(UserWorkspaceAccess.user_id == user_id)
    )
    return scope.visible(rows.scalars())


@router.get(
    "/admin-flags",
    response_model=list[uuid.UUID],
    dependencies=[Depends(require_super_admin)],
)
async def list_workspace_admin_flags(user_id: uuid.UUID, session: Session) -> list[uuid.UUID]:
    rows = await session.execute(
        select(UserWorkspaceAccess.workspace_id).where(
            UserWorkspaceAccess.user_id == user_id, UserWorkspaceAccess.is_admin.is_(True)
        )
    )
    return list(rows.scalars())


@router.post("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def grant_workspace_access(
    user_id: uuid.UUID, workspace_id: uuid.UUID, session: Session, scope: Scope, users: Users
) -> None:
    try:
        ensure_can_grant(scope, await _target(users, user_id), workspace_id)
    except AdminScopeDeniedError as exc:
        raise _forbidden(exc) from exc
    session.add(UserWorkspaceAccess(id=uuid.uuid4(), user_id=user_id, workspace_id=workspace_id))
    try:
        await session.commit()
    except IntegrityError:
        # Já concedido (idempotente) ou workspace inexistente.
        await session.rollback()


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_workspace_access(
    user_id: uuid.UUID, workspace_id: uuid.UUID, session: Session, scope: Scope, users: Users
) -> None:
    target = await _target(users, user_id)
    row = await _row(session, user_id, workspace_id)
    try:
        ensure_can_revoke(scope, target, workspace_id, target_is_admin=bool(row and row.is_admin))
    except AdminScopeDeniedError as exc:
        raise _forbidden(exc) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Acesso não existia.")
    await session.delete(row)
    await session.commit()


@router.put(
    "/{workspace_id}/admin",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_super_admin)],
)
async def set_workspace_admin(
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
    body: WorkspaceAdminFlag,
    session: Session,
    users: Users,
) -> None:
    """Liga ou desliga o admin do workspace; ligar também libera o acesso."""
    await _target(users, user_id)
    row = await _row(session, user_id, workspace_id)
    if row is None:
        if not body.is_admin:
            return
        row = UserWorkspaceAccess(id=uuid.uuid4(), user_id=user_id, workspace_id=workspace_id)
        session.add(row)
    row.is_admin = body.is_admin
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=404, detail="Workspace não encontrado.") from exc
