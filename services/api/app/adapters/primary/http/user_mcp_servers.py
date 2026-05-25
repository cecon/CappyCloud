"""HTTP adapter for user-scoped repository MCP servers."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.adapters.primary.http.deps import (
    get_authenticated_user,
    get_repository_repo,
    get_user_mcp_repo,
    get_user_repository_access_repo,
)
from app.application.use_cases.user_mcp_servers import (
    CreateUserMcpServer,
    DeleteUserMcpServer,
    ListUserMcpServers,
    RotateUserMcpServerToken,
    UpdateUserMcpServer,
    UserMcpRepositoryDeniedError,
    UserMcpServerNameTakenError,
    UserMcpServerNotFoundError,
)
from app.domain.entities import User, UserMcpServer
from app.ports.mcp_repository import UserMcpServerRepository
from app.ports.repositories import RepositoryRepository
from app.ports.user_access import UserRepositoryAccessRepository
from app.schemas_user_mcp import (
    UserMcpServerCreate,
    UserMcpServerOut,
    UserMcpServerSecretOut,
    UserMcpServerUpdate,
)

router = APIRouter(prefix="/mcp-servers", tags=["mcp-servers"])


def _serialize(server: UserMcpServer) -> UserMcpServerOut:
    return UserMcpServerOut.model_validate(server.__dict__)


def _serialize_secret(server: UserMcpServer, token: str) -> UserMcpServerSecretOut:
    return UserMcpServerSecretOut.model_validate({**server.__dict__, "token": token})


def _write_uc(
    repo: UserMcpServerRepository,
    repositories: RepositoryRepository,
    access: UserRepositoryAccessRepository,
) -> tuple[CreateUserMcpServer, UpdateUserMcpServer]:
    return CreateUserMcpServer(repo, repositories, access), UpdateUserMcpServer(
        repo,
        repositories,
        access,
    )


def _raise_use_case_error(exc: Exception) -> None:
    if isinstance(exc, UserMcpServerNameTakenError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if isinstance(exc, UserMcpServerNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, UserMcpRepositoryDeniedError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    raise exc


@router.get("", response_model=list[UserMcpServerOut])
async def list_user_mcp_servers(
    current: Annotated[User, Depends(get_authenticated_user)],
    repo: Annotated[UserMcpServerRepository, Depends(get_user_mcp_repo)],
) -> list[UserMcpServerOut]:
    rows = await ListUserMcpServers(repo).execute(current.id)
    return [_serialize(row) for row in rows]


@router.post("", response_model=UserMcpServerSecretOut, status_code=status.HTTP_201_CREATED)
async def create_user_mcp_server(
    body: UserMcpServerCreate,
    current: Annotated[User, Depends(get_authenticated_user)],
    repo: Annotated[UserMcpServerRepository, Depends(get_user_mcp_repo)],
    repositories: Annotated[RepositoryRepository, Depends(get_repository_repo)],
    access: Annotated[UserRepositoryAccessRepository, Depends(get_user_repository_access_repo)],
) -> UserMcpServerSecretOut:
    create_uc, _ = _write_uc(repo, repositories, access)
    try:
        created = await create_uc.execute(
            current=current,
            repository_id=body.repository_id,
            name=body.name,
            enabled=body.enabled,
        )
    except Exception as exc:
        _raise_use_case_error(exc)
    return _serialize_secret(created.server, created.token)


@router.put("/{server_id}", response_model=UserMcpServerOut)
async def update_user_mcp_server(
    server_id: uuid.UUID,
    body: UserMcpServerUpdate,
    current: Annotated[User, Depends(get_authenticated_user)],
    repo: Annotated[UserMcpServerRepository, Depends(get_user_mcp_repo)],
    repositories: Annotated[RepositoryRepository, Depends(get_repository_repo)],
    access: Annotated[UserRepositoryAccessRepository, Depends(get_user_repository_access_repo)],
) -> UserMcpServerOut:
    _, update_uc = _write_uc(repo, repositories, access)
    try:
        updated = await update_uc.execute(
            current=current,
            server_id=server_id,
            repository_id=body.repository_id,
            name=body.name,
            enabled=body.enabled,
        )
    except Exception as exc:
        _raise_use_case_error(exc)
    return _serialize(updated)


@router.post("/{server_id}/rotate-token", response_model=UserMcpServerSecretOut)
async def rotate_user_mcp_server_token(
    server_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    repo: Annotated[UserMcpServerRepository, Depends(get_user_mcp_repo)],
) -> UserMcpServerSecretOut:
    try:
        rotated = await RotateUserMcpServerToken(repo).execute(current=current, server_id=server_id)
    except UserMcpServerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _serialize_secret(rotated.server, rotated.token)


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_mcp_server(
    server_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    repo: Annotated[UserMcpServerRepository, Depends(get_user_mcp_repo)],
) -> None:
    deleted = await DeleteUserMcpServer(repo).execute(current=current, server_id=server_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP não encontrado.")
