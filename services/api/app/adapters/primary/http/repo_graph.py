"""Repository graph HTTP router.

The graph itself is built inside the sandbox sidecar, where `/repos/<slug>` lives.
The API only authenticates/authorizes and validates the response contract.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import get_authenticated_user, get_db_session
from app.adapters.secondary.sandbox_repo_graph_provider import (
    SandboxRepoGraphError,
    SandboxRepositoryGraphProvider,
)
from app.application.use_cases.repository_graph import GetRepositoryGraph
from app.application.use_cases.repository_graph_materialization import (
    enqueue_graph_materialization,
    invalidate_extractor,
    latest_materialized_commit_sha,
    load_materialized_repo_graph,
    resolve_repo_graph_commit_sha,
)
from app.application.use_cases.repository_graph_reconciliation import (
    RECONCILIATION_MODES,
    enqueue_graph_reconciliation,
    find_resolution_edge,
    latest_reconciliation_summary,
)
from app.domain.entities import User
from app.infrastructure.orm_models import Repository, Sandbox
from app.infrastructure.orm_models_access import UserRepositoryAccess
from app.schemas_repo_graph import RepositoryGraphOut

router = APIRouter(prefix="/repositories", tags=["repositories"])
_ALLOWED_EXTRACTORS = {"static_js", "static_roslyn", "static_sql", "llm_gap", "doc_import"}


class GraphInvalidateRequest(BaseModel):
    commit_sha: str
    source_extractor: str


class GraphReconcileRequest(BaseModel):
    commit_sha: str | None = None
    mode: str = "all"
    llm_model: str | None = None


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


@router.get(
    "/{repo_id}/graph",
    response_model=RepositoryGraphOut,
    response_model_exclude_none=True,
    responses={202: {"description": "Graph materialization queued"}},
)
async def get_repository_graph(
    repo_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    max_files: int = Query(default=1200, ge=50, le=5000),
    materialized: bool = Query(default=False),
    commit_sha: str | None = Query(default=None, min_length=7, max_length=64),
) -> RepositoryGraphOut | JSONResponse:
    repo = await _get_visible_repository(session, current, repo_id)
    if materialized:
        return await _get_materialized_repository_graph(
            session=session,
            repo=repo,
            commit_sha=commit_sha,
            max_files=max_files,
        )

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


@router.post("/{repo_id}/graph/materialize", status_code=status.HTTP_202_ACCEPTED)
async def enqueue_repository_graph_materialization(
    repo_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    max_files: int = Query(default=1200, ge=50, le=5000),
    commit_sha: str | None = Query(default=None, min_length=7, max_length=64),
) -> dict[str, Any]:
    repo = await _get_visible_repository(session, current, repo_id)
    resolved_commit = await _resolve_commit_sha(session, repo, commit_sha)
    if not resolved_commit:
        raise HTTPException(
            status_code=409,
            detail="Não foi possível resolver o commit do repositório para materialização.",
        )
    try:
        job_id = await enqueue_graph_materialization(
            session,
            repo=repo,
            commit_sha=resolved_commit,
            max_files=max_files,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await session.commit()
    return {"job_id": str(job_id), "status": "materializing", "commit_sha": resolved_commit}


@router.post("/{repo_id}/graph/invalidate")
async def invalidate_repository_graph_extractor(
    repo_id: uuid.UUID,
    payload: GraphInvalidateRequest,
    current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    repo = await _get_visible_repository(session, current, repo_id)
    commit_sha = payload.commit_sha.strip()
    source_extractor = payload.source_extractor.strip()
    if source_extractor not in _ALLOWED_EXTRACTORS:
        raise HTTPException(status_code=400, detail="source_extractor inválido.")
    result = await invalidate_extractor(
        session,
        repo_id=repo.id,
        commit_sha=commit_sha,
        source_extractor=source_extractor,
    )
    await session.commit()
    return {
        "repo_id": str(repo.id),
        "commit_sha": commit_sha,
        "source_extractor": source_extractor,
        **result,
    }


@router.post("/{repo_id}/graph/reconcile", status_code=status.HTTP_202_ACCEPTED)
async def enqueue_repository_graph_reconciliation(
    repo_id: uuid.UUID,
    payload: GraphReconcileRequest,
    current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    repo = await _get_visible_repository(session, current, repo_id)
    mode = payload.mode.strip()
    if mode not in RECONCILIATION_MODES:
        raise HTTPException(status_code=400, detail="mode inválido.")
    resolved_commit = await _resolve_commit_sha(session, repo, payload.commit_sha)
    if not resolved_commit:
        raise HTTPException(status_code=409, detail="Não foi possível resolver o commit.")
    try:
        job_id = await enqueue_graph_reconciliation(
            session,
            repo=repo,
            commit_sha=resolved_commit,
            mode=mode,
            llm_model=payload.llm_model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await session.commit()
    return {"job_id": str(job_id), "status": "reconciling", "commit_sha": resolved_commit}


@router.get("/{repo_id}/graph/reconciliation-summary")
async def get_repository_graph_reconciliation_summary(
    repo_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    commit_sha: str | None = Query(default=None, min_length=7, max_length=64),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    repo = await _get_visible_repository(session, current, repo_id)
    resolved_commit = await _resolve_commit_sha(session, repo, commit_sha)
    if not resolved_commit:
        raise HTTPException(status_code=409, detail="Não foi possível resolver o commit.")
    summary = await latest_reconciliation_summary(
        session,
        repo_id=repo.id,
        commit_sha=resolved_commit,
        limit=limit,
        offset=offset,
    )
    if summary is None:
        return {"repo_id": str(repo.id), "commit_sha": resolved_commit, "summary": None}
    return summary


@router.get("/{repo_id}/graph/resolution")
async def get_repository_graph_resolution(
    repo_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    commit_sha: str | None = Query(default=None, min_length=7, max_length=64),
    original_edge_key: str | None = Query(default=None, min_length=16, max_length=128),
    edge_id: int | None = Query(default=None, ge=1),
) -> dict[str, Any]:
    repo = await _get_visible_repository(session, current, repo_id)
    resolved_commit = await _resolve_commit_sha(session, repo, commit_sha)
    if not resolved_commit:
        raise HTTPException(status_code=409, detail="Não foi possível resolver o commit.")
    edge = await find_resolution_edge(
        session,
        repo_id=repo.id,
        commit_sha=resolved_commit,
        original_edge_key=original_edge_key,
        edge_id=edge_id,
    )
    if edge is None:
        raise HTTPException(status_code=404, detail="Reconciliação não encontrada.")
    return edge


async def _get_materialized_repository_graph(
    *,
    session: AsyncSession,
    repo: Repository,
    commit_sha: str | None,
    max_files: int,
) -> RepositoryGraphOut | JSONResponse:
    resolved_commit = await _resolve_commit_sha(session, repo, commit_sha)
    if not resolved_commit:
        raise HTTPException(
            status_code=409,
            detail=(
                "Informe commit_sha ou sincronize o repositório no sandbox para resolver o HEAD."
            ),
        )
    materialized_graph = await load_materialized_repo_graph(
        session,
        repo=repo,
        commit_sha=resolved_commit,
    )
    if materialized_graph is not None:
        return RepositoryGraphOut.model_validate(materialized_graph)
    try:
        job_id = await enqueue_graph_materialization(
            session,
            repo=repo,
            commit_sha=resolved_commit,
            max_files=max_files,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await session.commit()
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"job_id": str(job_id), "status": "materializing", "commit_sha": resolved_commit},
    )


async def _resolve_commit_sha(
    session: AsyncSession,
    repo: Repository,
    commit_sha: str | None,
) -> str | None:
    if commit_sha:
        return commit_sha.strip()
    if repo.sandbox_id and repo.sandbox_status == "cloned":
        sandbox = await session.get(Sandbox, repo.sandbox_id)
        if sandbox:
            try:
                return await resolve_repo_graph_commit_sha(
                    provider=SandboxRepositoryGraphProvider(),
                    repo=repo,
                    sandbox=sandbox,
                )
            except SandboxRepoGraphError:
                pass
    return await latest_materialized_commit_sha(session, repo.id)
