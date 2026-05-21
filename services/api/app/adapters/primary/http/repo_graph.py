"""Repository graph HTTP router.

The graph itself is built inside the sandbox sidecar, where `/repos/<slug>` lives.
The API only authenticates/authorizes and validates the response contract.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import get_authenticated_user, get_db_session
from app.adapters.secondary.sandbox_repo_graph_provider import (
    SandboxRepoGraphError,
    SandboxRepositoryGraphProvider,
)
from app.application.use_cases.repository_graph import GetRepositoryGraph
from app.domain.entities import User
from app.infrastructure.orm_models import Repository, Sandbox
from app.infrastructure.orm_models_access import UserRepositoryAccess
from app.schemas_repo_graph import RepositoryGraphOut

router = APIRouter(prefix="/repositories", tags=["repositories"])


async def _get_visible_repository(
    session: AsyncSession,
    current: User,
    repo_id: uuid.UUID,
) -> Repository:
    repo = await session.get(Repository, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repositório não encontrado")
    if current.is_admin:
        return repo

    access_row = await session.scalar(
        select(UserRepositoryAccess.id)
        .where(UserRepositoryAccess.user_id == current.id)
        .where(UserRepositoryAccess.repository_id == repo.id)
        .limit(1)
    )
    if not access_row:
        raise HTTPException(status_code=404, detail="Repositório não encontrado")
    return repo


def _graph_error_status(exc: SandboxRepoGraphError) -> int:
    message = str(exc).lower()
    if "não clonado" in message or "not cloned" in message:
        return 409
    if exc.status_code in {400, 404, 409}:
        return exc.status_code
    return 503


@router.get("/{repo_id}/graph", response_model=RepositoryGraphOut)
async def get_repository_graph(
    repo_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    max_files: int = Query(default=1200, ge=50, le=5000),
) -> RepositoryGraphOut:
    repo = await _get_visible_repository(session, current, repo_id)
    if not repo.sandbox_id:
        raise HTTPException(status_code=409, detail="Repositório sem sandbox associado")
    if repo.sandbox_status != "cloned":
        raise HTTPException(
            status_code=409,
            detail=f"Repositório ainda não está clonado no sandbox ({repo.sandbox_status}).",
        )

    sandbox = await session.get(Sandbox, repo.sandbox_id)
    if not sandbox:
        raise HTTPException(status_code=409, detail="Sandbox do repositório não encontrado")

    use_case = GetRepositoryGraph(SandboxRepositoryGraphProvider())
    try:
        data = await use_case.execute(
            sandbox_host=sandbox.host,
            sandbox_port=sandbox.session_port,
            slug=repo.slug,
            max_files=max_files,
        )
    except SandboxRepoGraphError as exc:
        raise HTTPException(status_code=_graph_error_status(exc), detail=str(exc)) from exc
    return RepositoryGraphOut.model_validate(data)
