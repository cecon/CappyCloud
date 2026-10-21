"""HTTP adapter administrativo para MCPs por sandbox (ADR-004 §6).

Endpoints (todos exigem ADMIN):
  GET    /admin/sandboxes/{sandbox_id}/mcps           → lista
  POST   /admin/sandboxes/{sandbox_id}/mcps           → cria
  PUT    /admin/sandboxes/{sandbox_id}/mcps/{id}      → atualiza
  DELETE /admin/sandboxes/{sandbox_id}/mcps/{id}      → remove
  GET    /admin/sandboxes/{sandbox_id}/mcps/export    → JSON openclaude

Criar, editar ou remover enfileira ``reconfigure_mcp``: o watchdog aplica no
sandbox na hora, sem esperar a próxima mensagem de chat (rotinas e webhooks
não reenviam a configuração).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import get_db_session, get_mcp_repo, require_role
from app.application.use_cases.mcp_servers import (
    CreateSandboxMcp,
    DeleteSandboxMcp,
    ExportSandboxMcpConfig,
    ListSandboxMcps,
    McpServerNameTakenError,
    McpServerNotFoundError,
    UpdateSandboxMcp,
)
from app.domain.entities import McpServer, UserRole
from app.infrastructure.orm_models import SandboxSyncQueue
from app.ports.mcp_repository import McpServerRepository
from app.schemas_mcp import McpServerCreate, McpServerOut, McpServerUpdate

router = APIRouter(
    prefix="/admin/sandboxes/{sandbox_id}/mcps",
    tags=["admin"],
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)


McpApplier = Callable[[uuid.UUID, dict], Awaitable[None]]


def get_mcp_applier(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> McpApplier:
    """Enfileira ``reconfigure_mcp`` para o watchdog aplicar no sandbox."""

    async def apply(sandbox_id: uuid.UUID, payload: dict) -> None:
        session.add(
            SandboxSyncQueue(
                id=uuid.uuid4(),
                sandbox_id=sandbox_id,
                operation="reconfigure_mcp",
                payload=payload,
                priority=4,
            )
        )
        await session.commit()

    return apply


Applier = Annotated[McpApplier, Depends(get_mcp_applier)]


def _serialize(mcp: McpServer) -> McpServerOut:
    return McpServerOut.model_validate(mcp.__dict__)


async def _apply_on_sandbox(
    apply: McpApplier, repo: McpServerRepository, sandbox_id: uuid.UUID
) -> None:
    await apply(sandbox_id, await ExportSandboxMcpConfig(repo).execute(sandbox_id))


@router.get("", response_model=list[McpServerOut])
async def list_mcps(
    sandbox_id: uuid.UUID,
    repo: Annotated[McpServerRepository, Depends(get_mcp_repo)],
) -> list[McpServerOut]:
    rows = await ListSandboxMcps(repo).execute(sandbox_id)
    return [_serialize(m) for m in rows]


@router.get("/export")
async def export_mcps(
    sandbox_id: uuid.UUID,
    repo: Annotated[McpServerRepository, Depends(get_mcp_repo)],
) -> dict:
    return await ExportSandboxMcpConfig(repo).execute(sandbox_id)


@router.post(
    "",
    response_model=McpServerOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_mcp(
    sandbox_id: uuid.UUID,
    body: McpServerCreate,
    repo: Annotated[McpServerRepository, Depends(get_mcp_repo)],
    apply: Applier,
) -> McpServerOut:
    try:
        mcp = await CreateSandboxMcp(repo).execute(
            sandbox_id=sandbox_id,
            name=body.name,
            command=body.command,
            args=body.args,
            env=body.env,
            enabled=body.enabled,
        )
    except McpServerNameTakenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await _apply_on_sandbox(apply, repo, sandbox_id)
    return _serialize(mcp)


@router.put("/{mcp_id}", response_model=McpServerOut)
async def update_mcp(
    sandbox_id: uuid.UUID,
    mcp_id: uuid.UUID,
    body: McpServerUpdate,
    repo: Annotated[McpServerRepository, Depends(get_mcp_repo)],
    apply: Applier,
) -> McpServerOut:
    try:
        mcp = await UpdateSandboxMcp(repo).execute(
            mcp_id=mcp_id,
            sandbox_id=sandbox_id,
            name=body.name,
            command=body.command,
            args=body.args,
            env=body.env,
            enabled=body.enabled,
        )
    except McpServerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except McpServerNameTakenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await _apply_on_sandbox(apply, repo, sandbox_id)
    return _serialize(mcp)


@router.delete("/{mcp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mcp(
    sandbox_id: uuid.UUID,
    mcp_id: uuid.UUID,
    repo: Annotated[McpServerRepository, Depends(get_mcp_repo)],
    apply: Applier,
) -> None:
    deleted = await DeleteSandboxMcp(repo).execute(mcp_id, sandbox_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP não encontrado.")
    await _apply_on_sandbox(apply, repo, sandbox_id)
