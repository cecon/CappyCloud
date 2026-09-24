"""Admin de workspaces (só super admin).

Um workspace agrupa repositórios do catálogo numa sandbox. Cada alteração
enfileira ``sync_workspace`` no ``sandbox_sync_queue``; o watchdog materializa
``/repos/workspaces/<slug>/`` no sandbox (CLAUDE.md, .claude/, repos/<alias>).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.adapters.primary.http.deps import get_db_session
from app.adapters.primary.http.deps_auth import require_super_admin
from app.infrastructure.orm_models import Repository, Sandbox, SandboxSyncQueue
from app.infrastructure.orm_models_workspaces import (
    UserWorkspaceAccess,
    Workspace,
    WorkspaceRepository,
)
from app.schemas_workspaces import (
    WorkspaceCreate,
    WorkspaceOut,
    WorkspaceRepositoryIn,
    WorkspaceRepositoryOut,
    WorkspaceUpdate,
)

router = APIRouter(
    prefix="/admin/workspaces",
    tags=["admin"],
    dependencies=[Depends(require_super_admin)],
)
access_router = APIRouter(
    prefix="/admin/users/{user_id}/access/workspaces",
    tags=["admin"],
    dependencies=[Depends(require_super_admin)],
)

Session = Annotated[AsyncSession, Depends(get_db_session)]


def _serialize(ws: Workspace) -> WorkspaceOut:
    return WorkspaceOut(
        id=ws.id,
        slug=ws.slug,
        name=ws.name,
        sandbox_id=ws.sandbox_id,
        claude_md=ws.claude_md,
        active=ws.active,
        sync_status=ws.sync_status,
        sync_error=ws.sync_error,
        last_sync_at=ws.last_sync_at,
        created_at=ws.created_at,
        repositories=[
            WorkspaceRepositoryOut(
                repository_id=link.repository_id,
                slug=link.repository.slug,
                name=link.repository.name,
                alias=link.alias,
                base_branch=link.base_branch,
                default_branch=link.repository.default_branch,
                sandbox_status=link.repository.sandbox_status,
            )
            for link in ws.repositories
        ],
    )


async def _load(session: AsyncSession, workspace_id: uuid.UUID) -> Workspace:
    ws = (
        await session.execute(
            select(Workspace)
            .where(Workspace.id == workspace_id)
            .options(
                selectinload(Workspace.repositories).selectinload(WorkspaceRepository.repository)
            )
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace não encontrado.")
    return ws


async def _set_repositories(
    session: AsyncSession, ws: Workspace, items: list[WorkspaceRepositoryIn]
) -> None:
    """Substitui os repositórios do workspace, validando sandbox e aliases."""
    ids = [item.repository_id for item in items]
    if len(set(ids)) != len(ids):
        raise HTTPException(status_code=400, detail="Repositório repetido no workspace.")
    found = await session.execute(select(Repository).where(Repository.id.in_(ids)))
    repos = {repo.id: repo for repo in found.scalars()}
    missing = [str(repo_id) for repo_id in ids if repo_id not in repos]
    if missing:
        raise HTTPException(
            status_code=404, detail=f"Repositórios não encontrados: {', '.join(missing)}"
        )
    wrong_sandbox = [repos[i].slug for i in ids if repos[i].sandbox_id != ws.sandbox_id]
    if wrong_sandbox:
        raise HTTPException(
            status_code=400,
            detail=f"Repositórios de outra sandbox: {', '.join(wrong_sandbox)}.",
        )
    aliases = [item.alias or repos[item.repository_id].slug for item in items]
    if len(set(aliases)) != len(aliases):
        raise HTTPException(status_code=400, detail="Alias repetido no workspace.")

    ws.repositories.clear()
    await session.flush()
    for item, alias in zip(items, aliases, strict=True):
        ws.repositories.append(
            WorkspaceRepository(
                id=uuid.uuid4(),
                repository_id=item.repository_id,
                alias=alias,
                base_branch=item.base_branch.strip(),
            )
        )


async def _enqueue_sync(session: AsyncSession, ws: Workspace) -> None:
    await session.flush()
    links = (
        await session.execute(
            select(WorkspaceRepository.alias, Repository.slug)
            .join(Repository, Repository.id == WorkspaceRepository.repository_id)
            .where(WorkspaceRepository.workspace_id == ws.id)
        )
    ).all()
    ws.sync_status = "pending"
    ws.sync_error = None
    session.add(
        SandboxSyncQueue(
            id=uuid.uuid4(),
            sandbox_id=ws.sandbox_id,
            operation="sync_workspace",
            payload={
                "slug": ws.slug,
                "claude_md": ws.claude_md,
                "repos": [{"alias": alias, "slug": slug} for alias, slug in links],
            },
            priority=4,
        )
    )


@router.get("", response_model=list[WorkspaceOut])
async def list_workspaces(session: Session) -> list[WorkspaceOut]:
    rows = (
        await session.execute(
            select(Workspace)
            .options(
                selectinload(Workspace.repositories).selectinload(WorkspaceRepository.repository)
            )
            .order_by(Workspace.name)
        )
    ).scalars()
    return [_serialize(ws) for ws in rows]


@router.get("/{workspace_id}", response_model=WorkspaceOut)
async def get_workspace(workspace_id: uuid.UUID, session: Session) -> WorkspaceOut:
    return _serialize(await _load(session, workspace_id))


@router.post("", response_model=WorkspaceOut, status_code=status.HTTP_201_CREATED)
async def create_workspace(body: WorkspaceCreate, session: Session) -> WorkspaceOut:
    if await session.get(Sandbox, body.sandbox_id) is None:
        raise HTTPException(status_code=404, detail="Sandbox não encontrada.")
    exists = await session.execute(select(Workspace.id).where(Workspace.slug == body.slug))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Já existe workspace '{body.slug}'.")
    ws = Workspace(
        id=uuid.uuid4(),
        slug=body.slug,
        name=body.name.strip(),
        sandbox_id=body.sandbox_id,
        claude_md=body.claude_md,
        active=True,
        repositories=[],
    )
    session.add(ws)
    await _set_repositories(session, ws, body.repositories)
    await _enqueue_sync(session, ws)
    await session.commit()
    return _serialize(await _load(session, ws.id))


@router.patch("/{workspace_id}", response_model=WorkspaceOut)
async def update_workspace(
    workspace_id: uuid.UUID, body: WorkspaceUpdate, session: Session
) -> WorkspaceOut:
    ws = await _load(session, workspace_id)
    if body.name is not None:
        ws.name = body.name.strip()
    if body.claude_md is not None:
        ws.claude_md = body.claude_md
    if body.active is not None:
        ws.active = body.active
    if body.repositories is not None:
        await _set_repositories(session, ws, body.repositories)
    await _enqueue_sync(session, ws)
    await session.commit()
    return _serialize(await _load(session, workspace_id))


@router.post("/{workspace_id}/sync", response_model=WorkspaceOut)
async def sync_workspace(workspace_id: uuid.UUID, session: Session) -> WorkspaceOut:
    ws = await _load(session, workspace_id)
    await _enqueue_sync(session, ws)
    await session.commit()
    return _serialize(await _load(session, workspace_id))


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(workspace_id: uuid.UUID, session: Session) -> None:
    ws = await _load(session, workspace_id)
    session.add(
        SandboxSyncQueue(
            id=uuid.uuid4(),
            sandbox_id=ws.sandbox_id,
            operation="remove_workspace",
            payload={"slug": ws.slug},
            priority=4,
        )
    )
    await session.delete(ws)
    await session.commit()


# ── Acesso de utilizadores ──────────────────────────────────────────────────


@access_router.get("", response_model=list[uuid.UUID])
async def list_workspace_access(user_id: uuid.UUID, session: Session) -> list[uuid.UUID]:
    rows = await session.execute(
        select(UserWorkspaceAccess.workspace_id).where(UserWorkspaceAccess.user_id == user_id)
    )
    return list(rows.scalars())


@access_router.post("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def grant_workspace_access(
    user_id: uuid.UUID, workspace_id: uuid.UUID, session: Session
) -> None:
    session.add(UserWorkspaceAccess(id=uuid.uuid4(), user_id=user_id, workspace_id=workspace_id))
    try:
        await session.commit()
    except IntegrityError:
        # Já concedido (idempotente) ou usuário/workspace inexistente.
        await session.rollback()


@access_router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_workspace_access(
    user_id: uuid.UUID, workspace_id: uuid.UUID, session: Session
) -> None:
    row = (
        await session.execute(
            select(UserWorkspaceAccess).where(
                UserWorkspaceAccess.user_id == user_id,
                UserWorkspaceAccess.workspace_id == workspace_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Acesso não existia.")
    await session.delete(row)
    await session.commit()
