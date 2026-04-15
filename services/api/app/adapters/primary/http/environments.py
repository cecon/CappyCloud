"""Environments HTTP adapter — CRUD de ambientes globais + status de containers.

Endpoints:
  GET  /environments          → lista todos os ambientes
  POST /environments          → cria ambiente novo
  GET  /environments/{id}     → detalhe de um ambiente
  DELETE /environments/{id}   → apaga ambiente (para container se a correr)
  GET  /environments/{id}/status → status do container Docker
  POST /environments/{id}/wake   → inicia container (fire-and-forget)
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.adapters.primary.http.deps import (
    get_agent,
    get_authenticated_user,
    get_create_repo_env_uc,
    get_delete_repo_env_uc,
    get_list_repo_envs_uc,
    get_repo_env_repo,
)
from app.application.use_cases.conversations import (
    CreateRepoEnvironment,
    DeleteRepoEnvironment,
    ListRepoEnvironments,
)
from app.domain.entities import User
from app.ports.agent import AgentPort
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
    """Remove um ambiente e para o container Docker se estiver a correr."""
    try:
        await uc.execute(env_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{env_id}/status")
async def get_environment_status(
    env_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    repo: Annotated[RepoEnvironmentRepository, Depends(get_repo_env_repo)],
    agent: Annotated[AgentPort, Depends(get_agent)],
) -> dict[str, object]:
    """Devolve o estado actual do container Docker para o ambiente."""
    env = await repo.get(env_id)
    if not env:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ambiente não encontrado."
        )
    return await asyncio.get_event_loop().run_in_executor(None, agent.get_env_status, env.slug)


@router.post("/{env_id}/wake")
async def wake_environment(
    env_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    repo: Annotated[RepoEnvironmentRepository, Depends(get_repo_env_repo)],
    agent: Annotated[AgentPort, Depends(get_agent)],
) -> dict[str, object]:
    """Inicia (ou reinicia) o container do ambiente (fire-and-forget).

    Devolve imediatamente. Faz polling a ``GET /environments/{id}/status``
    até status ser ``running``.
    """
    env = await repo.get(env_id)
    if not env:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ambiente não encontrado."
        )
    agent.wake_env(env.slug)
    return {"status": "starting"}
