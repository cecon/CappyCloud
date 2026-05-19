"""HTTP endpoints for conversation cancel and file exploration inside worktrees."""

from __future__ import annotations

import asyncio
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.conversation_worktree_paths import (
    WORKTREE_FROM_CONVERSATION,
    resolve_git_paths_from_worktree_row,
)
from app.adapters.primary.http.deps import get_agent, get_authenticated_user, get_db_session
from app.domain.entities import User
from app.infrastructure.sandbox_worktree_client import (
    SandboxWorktreeError,
    worktree_ls_files,
    worktree_read_file,
)
from app.ports.agent import AgentPort

router = APIRouter(prefix="/conversations", tags=["conversations"])


# ── Cancel ────────────────────────────────────────────────────────────────────


@router.post("/{conversation_id}/cancel")
async def cancel_conversation_task(
    conversation_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    agent: Annotated[AgentPort, Depends(get_agent)],
) -> dict:
    """Cancela a task activa da conversa."""
    conv_row = await db.execute(
        text("SELECT id FROM conversations WHERE id = :cid AND user_id = :uid"),
        {"cid": str(conversation_id), "uid": str(current.id)},
    )
    if not conv_row.fetchone():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada")

    try:
        cancelled = await asyncio.to_thread(agent.cancel_conversation, str(conversation_id))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    return {"cancelled": cancelled}


# ── Shared helper ─────────────────────────────────────────────────────────────


async def _get_worktree_container(
    conversation_id: uuid.UUID,
    user_id: str,
    db: AsyncSession,
) -> tuple[str, str]:
    """Retorna (container_name, worktree_path) para a conversa ou lança 404.

    Usa primeiro os caminhos em `cappy_sessions` (agente); se ainda não existir
    linha de sessão ou estiver desactualizada, faz fallback para `conversations.repos`
    e `conversations.session_root` definidos na criação da conversa.
    """
    row = await db.execute(
        text(WORKTREE_FROM_CONVERSATION),
        {"cid": str(conversation_id), "uid": user_id},
    )
    conv = row.fetchone()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada")
    worktree, _, _ = resolve_git_paths_from_worktree_row(conv, conversation_id)
    return "cappycloud-sandbox", worktree


# ── File listing ──────────────────────────────────────────────────────────────


@router.get("/{conversation_id}/files")
async def list_conversation_files(
    conversation_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Lista todos os ficheiros tracked do worktree (git ls-files)."""
    _, worktree_path = await _get_worktree_container(conversation_id, str(current.id), db)

    try:
        normalized, files = await worktree_ls_files(worktree_path)
    except SandboxWorktreeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return {"worktree_path": normalized, "files": files}


# ── File content ──────────────────────────────────────────────────────────────


@router.get("/{conversation_id}/file")
async def get_conversation_file(
    conversation_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    path: str = Query(..., description="Caminho relativo ao worktree"),
) -> dict:
    """Retorna o conteúdo de um ficheiro do worktree."""
    if ".." in path or path.startswith("/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Caminho inválido")

    _, worktree_path = await _get_worktree_container(conversation_id, str(current.id), db)

    try:
        rel_path, content = await worktree_read_file(worktree_path, path)
    except SandboxWorktreeError as exc:
        code = exc.status_code if exc.status_code >= 400 else status.HTTP_503_SERVICE_UNAVAILABLE
        raise HTTPException(status_code=code, detail=str(exc)) from exc

    return {"path": rel_path, "content": content}
