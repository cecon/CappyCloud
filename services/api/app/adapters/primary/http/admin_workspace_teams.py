"""Times de um workspace (relatório por time).

  GET    /admin/workspaces/{workspace_id}/teams            → times com nº de pessoas
  POST   /admin/workspaces/{workspace_id}/teams            → cria
  PATCH  /admin/workspaces/{workspace_id}/teams/{team_id}  → renomeia
  DELETE /admin/workspaces/{workspace_id}/teams/{team_id}  → apaga (pessoas ficam sem time)

ADMIN global e admin do workspace. Nome único por workspace, sem diferenciar
maiúsculas.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import get_db_session
from app.adapters.primary.http.deps_auth import get_admin_scope
from app.application.use_cases.admin_scope import AdminScope
from app.infrastructure.orm_models_workspaces import (
    UserWorkspaceAccess,
    Workspace,
    WorkspaceTeam,
)

router = APIRouter(prefix="/admin/workspaces/{workspace_id}/teams", tags=["admin"])

Session = Annotated[AsyncSession, Depends(get_db_session)]
Scope = Annotated[AdminScope, Depends(get_admin_scope)]

TEAM_NAME_MAX = 128


class TeamIn(BaseModel):
    name: str = Field(min_length=1, max_length=TEAM_NAME_MAX)

    @field_validator("name")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Informe o nome do time.")
        return value


class TeamOut(BaseModel):
    id: uuid.UUID
    name: str
    members: int


async def _ensure_workspace(
    session: AsyncSession, scope: AdminScope, workspace_id: uuid.UUID
) -> None:
    if not scope.allows(workspace_id):
        raise HTTPException(status_code=403, detail="Você não administra este workspace.")
    if await session.get(Workspace, workspace_id) is None:
        raise HTTPException(status_code=404, detail="Workspace não encontrado.")


async def _team(
    session: AsyncSession, workspace_id: uuid.UUID, team_id: uuid.UUID
) -> WorkspaceTeam:
    team = await session.get(WorkspaceTeam, team_id)
    if team is None or team.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Time não encontrado.")
    return team


async def _members(session: AsyncSession, team_id: uuid.UUID) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(UserWorkspaceAccess)
        .where(UserWorkspaceAccess.team_id == team_id)
    )
    return int(count or 0)


async def _save(session: AsyncSession) -> None:
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Já existe um time com esse nome.") from exc


@router.get("", response_model=list[TeamOut])
async def list_teams(workspace_id: uuid.UUID, session: Session, scope: Scope) -> list[TeamOut]:
    await _ensure_workspace(session, scope, workspace_id)
    members = (
        select(UserWorkspaceAccess.team_id, func.count().label("n"))
        .where(UserWorkspaceAccess.workspace_id == workspace_id)
        .group_by(UserWorkspaceAccess.team_id)
        .subquery()
    )
    rows = await session.execute(
        select(WorkspaceTeam.id, WorkspaceTeam.name, members.c.n)
        .outerjoin(members, members.c.team_id == WorkspaceTeam.id)
        .where(WorkspaceTeam.workspace_id == workspace_id)
        .order_by(func.lower(WorkspaceTeam.name))
    )
    return [TeamOut(id=row.id, name=row.name, members=int(row.n or 0)) for row in rows]


@router.post("", response_model=TeamOut, status_code=status.HTTP_201_CREATED)
async def create_team(
    workspace_id: uuid.UUID, body: TeamIn, session: Session, scope: Scope
) -> TeamOut:
    await _ensure_workspace(session, scope, workspace_id)
    team = WorkspaceTeam(id=uuid.uuid4(), workspace_id=workspace_id, name=body.name)
    session.add(team)
    await _save(session)
    return TeamOut(id=team.id, name=team.name, members=0)


@router.patch("/{team_id}", response_model=TeamOut)
async def rename_team(
    workspace_id: uuid.UUID, team_id: uuid.UUID, body: TeamIn, session: Session, scope: Scope
) -> TeamOut:
    await _ensure_workspace(session, scope, workspace_id)
    team = await _team(session, workspace_id, team_id)
    team.name = body.name
    await _save(session)
    return TeamOut(id=team.id, name=team.name, members=await _members(session, team.id))


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    workspace_id: uuid.UUID, team_id: uuid.UUID, session: Session, scope: Scope
) -> None:
    await _ensure_workspace(session, scope, workspace_id)
    team = await _team(session, workspace_id, team_id)
    # SQLite dos testes não aplica ON DELETE SET NULL sem PRAGMA; limpa aqui também.
    rows = await session.execute(
        select(UserWorkspaceAccess).where(UserWorkspaceAccess.team_id == team.id)
    )
    for access in rows.scalars():
        access.team_id = None
    await session.delete(team)
    await session.commit()
