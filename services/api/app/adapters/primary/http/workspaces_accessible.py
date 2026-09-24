"""Workspaces que o utilizador pode usar ao abrir uma conversa."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.adapters.primary.http.deps import get_authenticated_user, get_db_session
from app.domain.entities import User, UserRole
from app.infrastructure.orm_models_workspaces import (
    UserWorkspaceAccess,
    Workspace,
    WorkspaceRepository,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class AccessibleWorkspaceRepo(BaseModel):
    alias: str
    slug: str


class AccessibleWorkspace(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    sandbox_id: uuid.UUID
    ready: bool
    repositories: list[AccessibleWorkspaceRepo]


@router.get("/accessible", response_model=list[AccessibleWorkspace])
async def list_accessible_workspaces(
    current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[AccessibleWorkspace]:
    """Admin vê todos os ativos; utilizador comum, só os concedidos a ele."""
    query = (
        select(Workspace)
        .where(Workspace.active.is_(True))
        .options(selectinload(Workspace.repositories).selectinload(WorkspaceRepository.repository))
        .order_by(Workspace.name)
    )
    if current.role is not UserRole.ADMIN:
        query = query.join(
            UserWorkspaceAccess, UserWorkspaceAccess.workspace_id == Workspace.id
        ).where(UserWorkspaceAccess.user_id == current.id)
    rows = (await session.execute(query)).scalars()
    return [
        AccessibleWorkspace(
            id=ws.id,
            slug=ws.slug,
            name=ws.name,
            sandbox_id=ws.sandbox_id,
            ready=ws.sync_status == "synced" and bool(ws.repositories),
            repositories=[
                AccessibleWorkspaceRepo(alias=link.alias, slug=link.repository.slug)
                for link in ws.repositories
            ],
        )
        for ws in rows
    ]
