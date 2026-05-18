"""HTTP adapter administrativo para MCPs por sandbox (ADR-004 §6).

Endpoints (todos exigem ADMIN):
  GET    /admin/sandboxes/{sandbox_id}/mcps           → lista
  POST   /admin/sandboxes/{sandbox_id}/mcps           → cria
  PUT    /admin/sandboxes/{sandbox_id}/mcps/{id}      → atualiza
  DELETE /admin/sandboxes/{sandbox_id}/mcps/{id}      → remove
  GET    /admin/sandboxes/{sandbox_id}/mcps/export    → JSON openclaude
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.adapters.primary.http.deps import get_mcp_repo, require_role
from app.application.use_cases.mcp_servers import (
    CreateSandboxMcp,
    DeleteSandboxMcp,
    ExportSandboxMcpConfig,
    ListSandboxMcps,
    McpServerNameTakenError,
    McpServerNotFoundError,
    UpdateSandboxMcp,
)
from app.domain.entities import UserRole
from app.ports.mcp_repository import McpServerRepository
from app.schemas_mcp import McpServerCreate, McpServerOut, McpServerUpdate

router = APIRouter(
    prefix="/admin/sandboxes/{sandbox_id}/mcps",
    tags=["admin"],
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)


def _serialize(mcp) -> McpServerOut:  # type: ignore[no-untyped-def]
    return McpServerOut.model_validate(mcp.__dict__)


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
    return _serialize(mcp)


@router.put("/{mcp_id}", response_model=McpServerOut)
async def update_mcp(
    sandbox_id: uuid.UUID,
    mcp_id: uuid.UUID,
    body: McpServerUpdate,
    repo: Annotated[McpServerRepository, Depends(get_mcp_repo)],
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
    return _serialize(mcp)


@router.delete("/{mcp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mcp(
    sandbox_id: uuid.UUID,
    mcp_id: uuid.UUID,
    repo: Annotated[McpServerRepository, Depends(get_mcp_repo)],
) -> None:
    deleted = await DeleteSandboxMcp(repo).execute(mcp_id, sandbox_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP não encontrado.")
