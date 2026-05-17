"""HTTP adapter administrativo para sandboxes (ADR-004)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import require_role
from app.adapters.primary.http.deps_base import get_db_session
from app.adapters.secondary.persistence.sqlalchemy_sandbox_repo import (
    SQLAlchemySandboxRepository,
)
from app.adapters.secondary.sandbox_runtime import (
    DockerComposeSandboxRuntime,
    DockerSwarmSandboxRuntime,
)
from app.application.use_cases.admin_sandboxes import (
    BootSandbox,
    CloneSandbox,
    CreateSandbox,
    DeleteSandbox,
    GetSandbox,
    ListSandboxes,
    SandboxInUseError,
    SandboxNameTakenError,
    SandboxNotFoundError,
    StopSandbox,
    UpdateSandbox,
)
from app.domain.entities import Sandbox, SandboxRuntime, UserRole
from app.ports.repositories import SandboxRepository
from app.ports.sandbox_runtime import (
    RuntimeFailureError,
    SandboxRuntimeGateway,
)
from app.schemas import (
    SandboxAdminCreate,
    SandboxAdminUpdate,
    SandboxCloneBody,
    SandboxOut,
)

router = APIRouter(prefix="/admin/sandboxes", tags=["admin"])


def get_sandbox_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SandboxRepository:
    return SQLAlchemySandboxRepository(session)


def get_runtime_gateways() -> dict[SandboxRuntime, SandboxRuntimeGateway]:
    """Mapa de adapters de runtime disponíveis. Override em testes via
    ``app.dependency_overrides``."""
    return {
        SandboxRuntime.COMPOSE: DockerComposeSandboxRuntime(),
        SandboxRuntime.SWARM: DockerSwarmSandboxRuntime(),
    }


def _serialize(sb: Sandbox) -> SandboxOut:
    return SandboxOut(
        id=sb.id,
        name=sb.name,
        host=sb.host,
        grpc_port=sb.grpc_port,
        session_port=sb.session_port,
        status=sb.status,
        runtime=sb.runtime,
        image=sb.image,
        env_vars=dict(sb.env_vars),
        container_status=sb.container_status,
        created_at=sb.created_at,
    )


@router.get(
    "",
    response_model=list[SandboxOut],
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
async def list_sandboxes(
    repo: Annotated[SandboxRepository, Depends(get_sandbox_repo)],
) -> list[SandboxOut]:
    rows = await ListSandboxes(repo).execute()
    return [_serialize(s) for s in rows]


@router.get(
    "/{sandbox_id}",
    response_model=SandboxOut,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
async def get_sandbox(
    sandbox_id: uuid.UUID,
    repo: Annotated[SandboxRepository, Depends(get_sandbox_repo)],
) -> SandboxOut:
    try:
        sb = await GetSandbox(repo).execute(sandbox_id)
    except SandboxNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _serialize(sb)


@router.post(
    "",
    response_model=SandboxOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
async def create_sandbox(
    body: SandboxAdminCreate,
    repo: Annotated[SandboxRepository, Depends(get_sandbox_repo)],
) -> SandboxOut:
    try:
        sb = await CreateSandbox(repo).execute(
            name=body.name,
            runtime=body.runtime,
            image=body.image,
            env_vars=body.env_vars,
            host=body.host,
            grpc_port=body.grpc_port,
            session_port=body.session_port,
        )
    except SandboxNameTakenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _serialize(sb)


@router.patch(
    "/{sandbox_id}",
    response_model=SandboxOut,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
async def update_sandbox(
    sandbox_id: uuid.UUID,
    body: SandboxAdminUpdate,
    repo: Annotated[SandboxRepository, Depends(get_sandbox_repo)],
) -> SandboxOut:
    try:
        sb = await UpdateSandbox(repo).execute(
            sandbox_id,
            image=body.image,
            env_vars=body.env_vars,
            host=body.host,
            grpc_port=body.grpc_port,
            session_port=body.session_port,
            status=body.status,
        )
    except SandboxNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _serialize(sb)


@router.delete(
    "/{sandbox_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
async def delete_sandbox(
    sandbox_id: uuid.UUID,
    repo: Annotated[SandboxRepository, Depends(get_sandbox_repo)],
) -> None:
    try:
        await DeleteSandbox(repo).execute(sandbox_id)
    except SandboxNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SandboxInUseError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post(
    "/{sandbox_id}/clone",
    response_model=SandboxOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
async def clone_sandbox(
    sandbox_id: uuid.UUID,
    body: SandboxCloneBody,
    repo: Annotated[SandboxRepository, Depends(get_sandbox_repo)],
) -> SandboxOut:
    try:
        sb = await CloneSandbox(repo).execute(sandbox_id, body.new_name)
    except SandboxNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SandboxNameTakenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _serialize(sb)


@router.post(
    "/{sandbox_id}/boot",
    response_model=SandboxOut,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
async def boot_sandbox(
    sandbox_id: uuid.UUID,
    repo: Annotated[SandboxRepository, Depends(get_sandbox_repo)],
    runtimes: Annotated[dict[SandboxRuntime, SandboxRuntimeGateway], Depends(get_runtime_gateways)],
) -> SandboxOut:
    try:
        sb = await BootSandbox(repo, runtimes).execute(sandbox_id)
    except SandboxNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RuntimeFailureError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)) from exc
    return _serialize(sb)


@router.post(
    "/{sandbox_id}/stop",
    response_model=SandboxOut,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
async def stop_sandbox(
    sandbox_id: uuid.UUID,
    repo: Annotated[SandboxRepository, Depends(get_sandbox_repo)],
    runtimes: Annotated[dict[SandboxRuntime, SandboxRuntimeGateway], Depends(get_runtime_gateways)],
) -> SandboxOut:
    try:
        sb = await StopSandbox(repo, runtimes).execute(sandbox_id)
    except SandboxNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RuntimeFailureError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)) from exc
    return _serialize(sb)
