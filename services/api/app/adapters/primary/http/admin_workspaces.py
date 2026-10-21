"""Admin de workspaces.

Super admin cria, edita, sincroniza e exclui. Admin de workspace vê só os que
administra e, neles, muda apenas CLAUDE.md, chamado obrigatório e modo de
planejamento. ADMIN global comum só lê a lista (para liberar acessos).

Um workspace agrupa repositórios do catálogo numa sandbox. Cada alteração
enfileira ``sync_workspace`` no ``sandbox_sync_queue``; o watchdog materializa
``/repos/workspaces/<slug>/`` no sandbox (CLAUDE.md, .claude/, repos/<alias>).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.adapters.primary.http.deps import get_db_session
from app.adapters.primary.http.deps_auth import (
    get_admin_scope,
    get_workspace_manager_scope,
    require_super_admin,
)
from app.application.use_cases.admin_scope import AdminScope
from app.infrastructure.orm_models import Repository, Sandbox, SandboxSyncQueue
from app.infrastructure.orm_models_workspaces import Workspace, WorkspaceRepository
from app.schemas_workspaces import (
    WorkspaceCreate,
    WorkspaceOut,
    WorkspaceRepositoryIn,
    WorkspaceRepositoryOut,
    WorkspaceUpdate,
)

router = APIRouter(prefix="/admin/workspaces", tags=["admin"])

Session = Annotated[AsyncSession, Depends(get_db_session)]
SuperAdmin = [Depends(require_super_admin)]
# Campos que o admin de workspace pode mudar; o resto é do super admin.
WORKSPACE_ADMIN_FIELDS = {"claude_md", "plan_mode_enabled", "require_ticket"}


Manager = Annotated[AdminScope, Depends(get_workspace_manager_scope)]
# Ler a lista: qualquer admin (ADMIN global precisa dela para liberar acessos).
Reader = Annotated[AdminScope, Depends(get_admin_scope)]


def _ensure_in_scope(scope: AdminScope, workspace_id: uuid.UUID) -> None:
    if not scope.allows(workspace_id):
        raise HTTPException(status_code=403, detail="Você não administra este workspace.")


def _serialize(ws: Workspace) -> WorkspaceOut:
    return WorkspaceOut(
        id=ws.id,
        slug=ws.slug,
        name=ws.name,
        sandbox_id=ws.sandbox_id,
        claude_md=ws.claude_md,
        active=ws.active,
        plan_mode_enabled=ws.plan_mode_enabled,
        require_ticket=ws.require_ticket,
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
                read_only=link.read_only,
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
                read_only=item.read_only,
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
async def list_workspaces(session: Session, scope: Reader) -> list[WorkspaceOut]:
    stmt = (
        select(Workspace)
        .options(selectinload(Workspace.repositories).selectinload(WorkspaceRepository.repository))
        .order_by(Workspace.name)
    )
    if scope.workspace_ids is not None:
        stmt = stmt.where(Workspace.id.in_(scope.workspace_ids))
    return [_serialize(ws) for ws in (await session.execute(stmt)).scalars()]


@router.get("/{workspace_id}", response_model=WorkspaceOut)
async def get_workspace(workspace_id: uuid.UUID, session: Session, scope: Reader) -> WorkspaceOut:
    _ensure_in_scope(scope, workspace_id)
    return _serialize(await _load(session, workspace_id))


@router.post(
    "",
    response_model=WorkspaceOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=SuperAdmin,
)
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
        plan_mode_enabled=body.plan_mode_enabled,
        require_ticket=body.require_ticket,
        repositories=[],
    )
    session.add(ws)
    await _set_repositories(session, ws, body.repositories)
    await _enqueue_sync(session, ws)
    await session.commit()
    return _serialize(await _load(session, ws.id))


@router.patch("/{workspace_id}", response_model=WorkspaceOut)
async def update_workspace(
    workspace_id: uuid.UUID, body: WorkspaceUpdate, session: Session, scope: Manager
) -> WorkspaceOut:
    _ensure_in_scope(scope, workspace_id)
    extra = body.model_fields_set - WORKSPACE_ADMIN_FIELDS
    if not scope.is_global and extra:
        raise HTTPException(
            status_code=403,
            detail="Admin de workspace só altera CLAUDE.md, chamado obrigatório e modo de "
            "planejamento.",
        )
    ws = await _load(session, workspace_id)
    if body.name is not None:
        ws.name = body.name.strip()
    if body.claude_md is not None:
        ws.claude_md = body.claude_md
    if body.active is not None:
        ws.active = body.active
    if body.plan_mode_enabled is not None:
        ws.plan_mode_enabled = body.plan_mode_enabled
    if body.require_ticket is not None:
        ws.require_ticket = body.require_ticket
    if body.repositories is not None:
        await _set_repositories(session, ws, body.repositories)
    await _enqueue_sync(session, ws)
    await session.commit()
    return _serialize(await _load(session, workspace_id))


@router.post("/{workspace_id}/sync", response_model=WorkspaceOut, dependencies=SuperAdmin)
async def sync_workspace(workspace_id: uuid.UUID, session: Session) -> WorkspaceOut:
    ws = await _load(session, workspace_id)
    await _enqueue_sync(session, ws)
    await session.commit()
    return _serialize(await _load(session, workspace_id))


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=SuperAdmin)
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
