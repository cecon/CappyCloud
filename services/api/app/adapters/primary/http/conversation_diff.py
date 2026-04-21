"""HTTP endpoints for conversation status, diff view, and inline diff comments."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import get_authenticated_user, get_db_session
from app.domain.entities import User

router = APIRouter(prefix="/conversations", tags=["conversations"])


# ── Status ────────────────────────────────────────────────────────────────────


@router.get("/{conversation_id}/status")
async def get_conversation_status(
    conversation_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Estado actual do agente para esta conversa.

    O frontend usa isto ao abrir/recarregar o chat para saber onde retomar.
    """
    conv_row = await db.execute(
        text("SELECT id FROM conversations WHERE id = :cid AND user_id = :uid"),
        {"cid": str(conversation_id), "uid": str(current.id)},
    )
    if not conv_row.fetchone():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada")

    task_row = await db.execute(
        text(
            "SELECT id, status, last_event_at FROM agent_tasks "
            "WHERE conversation_id = :cid ORDER BY created_at DESC LIMIT 1"
        ),
        {"cid": str(conversation_id)},
    )
    task = task_row.fetchone()
    agent_status = task.status if task else "idle"
    task_id = str(task.id) if task else None
    last_event_at = task.last_event_at if task else None

    cursor = None
    if task_id:
        ev_row = await db.execute(
            text("SELECT MAX(id) AS max_id FROM agent_events WHERE task_id = :tid"),
            {"tid": task_id},
        )
        ev = ev_row.fetchone()
        cursor = ev.max_id if ev else None

    env_status = "running"

    return {
        "env_status": env_status,
        "agent_status": agent_status,
        "current_task_id": task_id,
        "last_event_at": last_event_at.isoformat() if last_event_at else None,
        "cursor": cursor,
    }


# ── Diff view ─────────────────────────────────────────────────────────────────


@router.get("/{conversation_id}/diff")
async def get_conversation_diff(
    conversation_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Diff do worktree actual em relação ao branch base."""
    row = await db.execute(
        text(
            "SELECT "
            "  cs.session_root, "
            "  cs.repos->0->>'worktree_path' AS worktree_path, "
            "  cs.repos->0->>'base_branch'   AS base_branch "
            "FROM conversations c "
            "LEFT JOIN cappy_sessions cs ON cs.chat_id = c.id::text "
            "WHERE c.id = :cid AND c.user_id = :uid"
        ),
        {"cid": str(conversation_id), "uid": str(current.id)},
    )
    conv = row.fetchone()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada")

    base_branch = conv.base_branch or "main"
    worktree = conv.worktree_path or conv.session_root
    if not worktree:
        return {"base_branch": base_branch, "stats": {"added": 0, "removed": 0}, "files": []}

    try:
        import docker

        client = docker.from_env()
        container = client.containers.get("cappycloud-sandbox")
        _, output = container.exec_run(
            ["git", "-C", worktree, "diff", f"{base_branch}..HEAD"],
        )
        diff_text = output.decode("utf-8", errors="replace") if output else ""
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Erro ao obter diff: {exc}"
        ) from exc

    return _parse_diff(diff_text, base_branch)


def _parse_diff(diff_text: str, base_branch: str) -> dict:
    """Parse unified diff output into structured format."""
    import re

    files = []
    total_added = total_removed = 0
    current_file: dict | None = None
    current_hunk: dict | None = None

    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            if current_file:
                if current_hunk:
                    current_file["hunks"].append(current_hunk)
                files.append(current_file)
            current_file = {"path": "", "hunks": [], "added": 0, "removed": 0}
            current_hunk = None
        elif line.startswith("+++ b/") and current_file is not None:
            current_file["path"] = line[6:]
        elif line.startswith("@@") and current_file is not None:
            if current_hunk:
                current_file["hunks"].append(current_hunk)
            m = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if m:
                current_hunk = {
                    "old_start": int(m.group(1)),
                    "new_start": int(m.group(2)),
                    "lines": [],
                }
        elif current_hunk is not None:
            if line.startswith("+") and not line.startswith("+++"):
                current_hunk["lines"].append({"type": "add", "content": line[1:]})
                if current_file:
                    current_file["added"] += 1
                total_added += 1
            elif line.startswith("-") and not line.startswith("---"):
                current_hunk["lines"].append({"type": "remove", "content": line[1:]})
                if current_file:
                    current_file["removed"] += 1
                total_removed += 1
            else:
                current_hunk["lines"].append(
                    {"type": "context", "content": line[1:] if line.startswith(" ") else line}
                )

    if current_hunk and current_file:
        current_file["hunks"].append(current_hunk)
    if current_file:
        files.append(current_file)

    return {
        "base_branch": base_branch,
        "stats": {"added": total_added, "removed": total_removed},
        "files": files,
    }


# ── Diff comments ─────────────────────────────────────────────────────────────


class DiffCommentIn(BaseModel):
    file_path: str = Field(min_length=1)
    line: int = Field(ge=1)
    content: str = Field(min_length=1, max_length=4096)


@router.post("/{conversation_id}/diff-comments", status_code=status.HTTP_201_CREATED)
async def add_diff_comment(
    conversation_id: uuid.UUID,
    body: DiffCommentIn,
    current: Annotated[User, Depends(get_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Adiciona comentário inline num ficheiro do diff."""
    import uuid as _uuid

    conv_row = await db.execute(
        text("SELECT id FROM conversations WHERE id = :cid AND user_id = :uid"),
        {"cid": str(conversation_id), "uid": str(current.id)},
    )
    if not conv_row.fetchone():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada")

    comment_id = str(_uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO diff_comments (id, conversation_id, file_path, line, content) "
            "VALUES (:id, :cid, :fp, :ln, :content)"
        ),
        {
            "id": comment_id,
            "cid": str(conversation_id),
            "fp": body.file_path,
            "ln": body.line,
            "content": body.content,
        },
    )
    await db.commit()
    return {"id": comment_id, "conversation_id": str(conversation_id), "bundled": False}


@router.get("/{conversation_id}/diff-comments")
async def list_diff_comments(
    conversation_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    pending_only: bool = Query(default=True),
) -> list[dict]:
    """Lista comentários de diff da conversa."""
    conv_row = await db.execute(
        text("SELECT id FROM conversations WHERE id = :cid AND user_id = :uid"),
        {"cid": str(conversation_id), "uid": str(current.id)},
    )
    if not conv_row.fetchone():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada")

    q = (
        "SELECT id, file_path, line, content, bundled_at, created_at "
        "FROM diff_comments WHERE conversation_id = :cid"
    )
    if pending_only:
        q += " AND bundled_at IS NULL"
    q += " ORDER BY file_path, line"

    rows = await db.execute(text(q), {"cid": str(conversation_id)})
    return [
        {
            "id": str(r.id),
            "file_path": r.file_path,
            "line": r.line,
            "content": r.content,
            "bundled": r.bundled_at is not None,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows.fetchall()
    ]
