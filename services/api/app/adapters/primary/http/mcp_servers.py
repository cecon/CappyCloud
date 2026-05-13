"""MCP Servers HTTP router — CRUD de servidores MCP por utilizador.

Endpoints:
  GET    /mcp-servers            → lista MCPs do utilizador autenticado
  POST   /mcp-servers            → cria novo MCP
  PUT    /mcp-servers/{id}       → atualiza MCP existente
  DELETE /mcp-servers/{id}       → remove MCP
  GET    /mcp-servers/export     → exporta config no formato openclaude
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.adapters.primary.http.deps import get_authenticated_user, get_mcp_repo
from app.application.use_cases.mcp_servers import (
    CreateMcpServer,
    DeleteMcpServer,
    ExportMcpConfig,
    ListMcpServers,
    UpdateMcpServer,
)
from app.domain.entities import User
from app.ports.mcp_repository import McpServerRepository
from app.schemas import McpServerCreate, McpServerOut, McpServerUpdate

router = APIRouter(prefix="/mcp-servers", tags=["mcp-servers"])


@router.get("", response_model=list[McpServerOut])
async def list_mcp_servers(
    current: Annotated[User, Depends(get_authenticated_user)],
    repo: Annotated[McpServerRepository, Depends(get_mcp_repo)],
) -> list[McpServerOut]:
    """Lista todos os servidores MCP do utilizador autenticado."""
    uc = ListMcpServers(repo)
    servers = await uc.execute(current.id)
    return [McpServerOut.model_validate(s.__dict__) for s in servers]


@router.get("/export")
async def export_mcp_config(
    current: Annotated[User, Depends(get_authenticated_user)],
    repo: Annotated[McpServerRepository, Depends(get_mcp_repo)],
) -> dict:
    """Exporta configuração de MCPs no formato mcpServers do openclaude."""
    uc = ExportMcpConfig(repo)
    return await uc.execute(current.id)


@router.post("", response_model=McpServerOut, status_code=status.HTTP_201_CREATED)
async def create_mcp_server(
    body: McpServerCreate,
    current: Annotated[User, Depends(get_authenticated_user)],
    repo: Annotated[McpServerRepository, Depends(get_mcp_repo)],
) -> McpServerOut:
    """Cria um novo servidor MCP para o utilizador autenticado."""
    uc = CreateMcpServer(repo)
    try:
        mcp = await uc.execute(
            user_id=current.id,
            name=body.name,
            command=body.command,
            args=body.args,
            env=body.env,
            enabled=body.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return McpServerOut.model_validate(mcp.__dict__)


@router.put("/{mcp_id}", response_model=McpServerOut)
async def update_mcp_server(
    mcp_id: uuid.UUID,
    body: McpServerUpdate,
    current: Annotated[User, Depends(get_authenticated_user)],
    repo: Annotated[McpServerRepository, Depends(get_mcp_repo)],
) -> McpServerOut:
    """Atualiza um servidor MCP existente."""
    uc = UpdateMcpServer(repo)
    try:
        mcp = await uc.execute(
            mcp_id=mcp_id,
            user_id=current.id,
            name=body.name,
            command=body.command,
            args=body.args,
            env=body.env,
            enabled=body.enabled,
        )
    except ValueError as exc:
        detail = str(exc)
        code = status.HTTP_409_CONFLICT if "já existe" in detail else status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=code, detail=detail) from exc
    return McpServerOut.model_validate(mcp.__dict__)


@router.delete("/{mcp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mcp_server(
    mcp_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    repo: Annotated[McpServerRepository, Depends(get_mcp_repo)],
) -> None:
    """Remove um servidor MCP."""
    uc = DeleteMcpServer(repo)
    deleted = await uc.execute(mcp_id, current.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP não encontrado.")
