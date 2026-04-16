"""HTTP endpoints for conversation cancel and file exploration inside worktrees."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import get_authenticated_user, get_db_session
from app.domain.entities import User

router = APIRouter(prefix="/conversations", tags=["conversations"])


# ── Cancel ────────────────────────────────────────────────────────────────────


@router.post("/{conversation_id}/cancel")
async def cancel_conversation_task(
    conversation_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Cancela a task activa da conversa."""
    conv_row = await db.execute(
        text("SELECT id FROM conversations WHERE id = :cid AND user_id = :uid"),
        {"cid": str(conversation_id), "uid": str(current.id)},
    )
    if not conv_row.fetchone():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada")

    try:
        agent = request.app.state.agent
        cancelled = agent.cancel_conversation(str(conversation_id))
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
    """Retorna (container_name, worktree_path) para a conversa ou lança 404."""
    row = await db.execute(
        text(
            "SELECT cs.worktree_path "
            "FROM conversations c "
            "LEFT JOIN cappy_sessions cs ON cs.chat_id = c.id::text "
            "WHERE c.id = :cid AND c.user_id = :uid"
        ),
        {"cid": str(conversation_id), "uid": user_id},
    )
    conv = row.fetchone()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada")
    if not conv.worktree_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sem worktree activa para esta conversa",
        )
    return "cappycloud-sandbox", conv.worktree_path


# ── File listing ──────────────────────────────────────────────────────────────


@router.get("/{conversation_id}/files")
async def list_conversation_files(
    conversation_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Lista todos os ficheiros tracked do worktree (git ls-files)."""
    container_id, worktree_path = await _get_worktree_container(
        conversation_id, str(current.id), db
    )

    try:
        import docker

        client = docker.from_env()
        container = client.containers.get(container_id)
        _, output = container.exec_run(
            ["git", "-C", worktree_path, "ls-files"],
        )
        raw = output.decode("utf-8", errors="replace") if output else ""
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Erro ao listar ficheiros: {exc}",
        ) from exc

    files = [f for f in raw.splitlines() if f.strip()]
    return {"worktree_path": worktree_path, "files": files}


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

    container_id, worktree_path = await _get_worktree_container(
        conversation_id, str(current.id), db
    )

    full_path = f"{worktree_path}/{path}"
    try:
        import docker

        client = docker.from_env()
        container = client.containers.get(container_id)
        exit_code, output = container.exec_run(["cat", full_path])
        if exit_code != 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ficheiro não encontrado: {path}",
            )
        content = output.decode("utf-8", errors="replace") if output else ""
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Erro ao ler ficheiro: {exc}",
        ) from exc

    return {"path": path, "content": content}
