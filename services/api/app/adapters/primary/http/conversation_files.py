"""HTTP endpoints for conversation cancel and file exploration inside worktrees."""

from __future__ import annotations

import asyncio
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.conversation_repos import load_conversation_repos
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


# ── File listing ──────────────────────────────────────────────────────────────


@router.get("/{conversation_id}/files")
async def list_conversation_files(
    conversation_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Arquivos tracked (git ls-files) de todos os repositórios da conversa.

    Com vários repositórios cada caminho começa pelo alias (a raiz mostra os
    repositórios como pastas); os somente leitura também aparecem.
    """
    conv = await load_conversation_repos(db, conversation_id, current.id)
    files: list[str] = []
    worktree_path = ""
    for repo in conv.repos:
        try:
            normalized, repo_files = await worktree_ls_files(repo.worktree_path)
        except SandboxWorktreeError as exc:
            if not conv.prefixed:
                raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
            continue
        worktree_path = worktree_path or normalized
        files.extend(conv.to_ui_path(repo, rel) for rel in repo_files)
    return {"worktree_path": worktree_path, "files": files}


# ── File content ──────────────────────────────────────────────────────────────


@router.get("/{conversation_id}/file")
async def get_conversation_file(
    conversation_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    path: str = Query(..., description="Caminho relativo ao worktree"),
) -> dict:
    """Retorna o conteúdo de um ficheiro de um dos repositórios da conversa."""
    if ".." in path or path.startswith("/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Caminho inválido")

    conv = await load_conversation_repos(db, conversation_id, current.id)
    repo, rel = conv.from_ui_path(path)
    try:
        rel_path, content = await worktree_read_file(repo.worktree_path, rel)
    except SandboxWorktreeError as exc:
        code = exc.status_code if exc.status_code >= 400 else status.HTTP_503_SERVICE_UNAVAILABLE
        raise HTTPException(status_code=code, detail=str(exc)) from exc

    return {"path": conv.to_ui_path(repo, rel_path), "content": content}
