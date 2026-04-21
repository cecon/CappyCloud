"""Repositories admin HTTP router — CRUD de repos e disparo de sync no sandbox."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import get_authenticated_user, get_db_session
from app.domain.entities import User
from app.infrastructure.orm_models import Repository, Sandbox, SandboxSyncQueue
from app.schemas import RepositoryCreate, RepositoryOut

router = APIRouter(prefix="/repositories", tags=["repositories"])


@router.get("", response_model=list[RepositoryOut])
async def list_repositories(
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[RepositoryOut]:
    rows = await session.execute(select(Repository).order_by(Repository.name))
    return [RepositoryOut.model_validate(r) for r in rows.scalars()]


@router.post("", response_model=RepositoryOut, status_code=201)
async def create_repository(
    body: RepositoryCreate,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RepositoryOut:
    sandbox_id = body.sandbox_id
    if sandbox_id is None:
        row = await session.execute(
            select(Sandbox).where(Sandbox.status == "active").order_by(Sandbox.created_at).limit(1)
        )
        default_sandbox = row.scalar_one_or_none()
        if default_sandbox:
            sandbox_id = default_sandbox.id

    repo = Repository(
        id=uuid.uuid4(),
        slug=body.slug,
        name=body.name,
        clone_url=body.clone_url,
        default_branch=body.default_branch,
        provider_id=body.provider_id,
        sandbox_id=sandbox_id,
    )
    session.add(repo)
    await session.commit()
    await session.refresh(repo)
    return RepositoryOut.model_validate(repo)


@router.post("/{repo_id}/sync", status_code=202)
async def enqueue_sync(
    repo_id: uuid.UUID,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Enfileira clone/update do repo no sandbox via sandbox_sync_queue."""
    repo = await session.get(Repository, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repositório não encontrado")
    if not repo.sandbox_id:
        raise HTTPException(status_code=400, detail="Repositório não possui sandbox associado")

    item = SandboxSyncQueue(
        id=uuid.uuid4(),
        sandbox_id=repo.sandbox_id,
        operation="clone_repo",
        payload={
            "slug": repo.slug,
            "clone_url": repo.clone_url,
            "default_branch": repo.default_branch,
        },
        priority=5,
    )
    session.add(item)
    await session.commit()
    return {"queued": True, "sync_item_id": str(item.id)}


@router.delete("/{repo_id}", status_code=204)
async def delete_repository(
    repo_id: uuid.UUID,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    repo = await session.get(Repository, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repositório não encontrado")

    if repo.sandbox_id and repo.sandbox_status == "cloned":
        item = SandboxSyncQueue(
            id=uuid.uuid4(),
            sandbox_id=repo.sandbox_id,
            operation="remove_repo",
            payload={"slug": repo.slug, "sandbox_path": repo.sandbox_path},
            priority=3,
        )
        session.add(item)

    await session.delete(repo)
    await session.commit()
