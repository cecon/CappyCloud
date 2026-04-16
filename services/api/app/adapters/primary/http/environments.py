"""Environments HTTP adapter — CRUD de ambientes de repositório.

Endpoints:
  GET  /environments          → lista todos os ambientes
  POST /environments          → cria ambiente novo
  GET  /environments/{id}     → detalhe de um ambiente
  DELETE /environments/{id}   → apaga o registo do ambiente no banco
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.adapters.primary.http.deps import (
    get_authenticated_user,
    get_create_repo_env_uc,
    get_delete_repo_env_uc,
    get_list_repo_envs_uc,
    get_repo_env_repo,
)
from app.application.use_cases.repo_environments import (
    CreateRepoEnvironment,
    DeleteRepoEnvironment,
    ListRepoEnvironments,
)
from app.domain.entities import User
from app.ports.repositories import RepoEnvironmentRepository
from app.schemas import RepoEnvCreate, RepoEnvOut

router = APIRouter(prefix="/environments", tags=["environments"])


@router.get("", response_model=list[RepoEnvOut])
async def list_environments(
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[ListRepoEnvironments, Depends(get_list_repo_envs_uc)],
) -> list[RepoEnvOut]:
    """Lista todos os ambientes de repositório globais."""
    envs = await uc.execute()
    return [RepoEnvOut.model_validate(e) for e in envs]


@router.post("", response_model=RepoEnvOut, status_code=status.HTTP_201_CREATED)
async def create_environment(
    body: RepoEnvCreate,
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[CreateRepoEnvironment, Depends(get_create_repo_env_uc)],
) -> RepoEnvOut:
    """Cria um novo ambiente de repositório global."""
    try:
        env = await uc.execute(
            slug=body.slug,
            name=body.name,
            repo_url=body.repo_url,
            branch=body.branch,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    result: RepoEnvOut = RepoEnvOut.model_validate(env)
    return result


@router.get("/{env_id}", response_model=RepoEnvOut)
async def get_environment(
    env_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    repo: Annotated[RepoEnvironmentRepository, Depends(get_repo_env_repo)],
) -> RepoEnvOut:
    """Detalhe de um ambiente pelo seu ID."""
    env = await repo.get(env_id)
    if not env:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ambiente não encontrado."
        )
    env_out: RepoEnvOut = RepoEnvOut.model_validate(env)
    return env_out


@router.delete("/{env_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_environment(
    env_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[DeleteRepoEnvironment, Depends(get_delete_repo_env_uc)],
) -> None:
    """Remove o registo do ambiente do banco de dados."""
    try:
        await uc.execute(env_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
