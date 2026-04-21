"""HTTP adapter for AgentTask management — list, trigger, and view events."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import get_authenticated_user, get_db_session
from app.domain.entities import User

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskTriggerBody(BaseModel):
    env_slug: str = Field(min_length=1, max_length=128)
    prompt: str = Field(min_length=1)
    triggered_by: str = Field(default="manual")
    conversation_id: str | None = None


@router.get("")
async def list_tasks(
    current: Annotated[User, Depends(get_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    env_slug: str | None = Query(default=None),
    task_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, le=200),
) -> list[dict]:
    """Lista tasks acessíveis pelo utilizador autenticado."""
    q = """
        SELECT at.id, at.env_slug, at.status, at.triggered_by, at.prompt,
               at.started_at, at.completed_at, at.last_event_at, at.created_at,
               at.conversation_id
        FROM agent_tasks at
        LEFT JOIN conversations c ON c.id = at.conversation_id
        WHERE (c.user_id = :uid OR at.conversation_id IS NULL)
    """
    params: dict = {"uid": str(current.id)}

    if env_slug:
        q += " AND at.env_slug = :slug"
        params["slug"] = env_slug
    if task_status:
        q += " AND at.status = :status"
        params["status"] = task_status

    q += " ORDER BY at.created_at DESC LIMIT :limit"
    params["limit"] = limit

    rows = await db.execute(text(q), params)
    return [
        {
            "id": str(r.id),
            "env_slug": r.env_slug,
            "status": r.status,
            "triggered_by": r.triggered_by,
            "prompt": r.prompt[:200] + ("…" if len(r.prompt) > 200 else ""),
            "conversation_id": str(r.conversation_id) if r.conversation_id else None,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "last_event_at": r.last_event_at.isoformat() if r.last_event_at else None,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows.fetchall()
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
async def trigger_task(
    body: TaskTriggerBody,
    current: Annotated[User, Depends(get_authenticated_user)],
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Dispara nova task de agente via CLI ou API."""
    try:
        agent = request.app.state.agent
        task_id = await agent.dispatch(
            prompt=body.prompt,
            conversation_id=body.conversation_id,
            triggered_by=body.triggered_by or "manual",
            trigger_payload={"triggered_via": "api", "user_id": str(current.id)},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Erro ao disparar task: {exc}",
        ) from exc

    return {"task_id": task_id, "env_slug": body.env_slug, "status": "pending"}


@router.get("/{task_id}/events")
async def get_task_events(
    task_id: str,
    current: Annotated[User, Depends(get_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    after: int | None = Query(default=None, description="Cursor: retorna eventos com id > after"),
    limit: int = Query(default=100, le=500),
) -> list[dict]:
    """Eventos de uma task (paginados por cursor)."""
    # Verify access: task must belong to a conversation owned by user OR have no conversation
    access_row = await db.execute(
        text(
            """
            SELECT at.id FROM agent_tasks at
            LEFT JOIN conversations c ON c.id = at.conversation_id
            WHERE at.id = :tid AND (c.user_id = :uid OR at.conversation_id IS NULL)
            """
        ),
        {"tid": task_id, "uid": str(current.id)},
    )
    if not access_row.fetchone():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task não encontrada.")

    q = "SELECT id, event_type, data, created_at FROM agent_events WHERE task_id = :tid"
    params: dict = {"tid": task_id}
    if after is not None:
        q += " AND id > :after"
        params["after"] = after
    q += " ORDER BY id LIMIT :limit"
    params["limit"] = limit

    rows = await db.execute(text(q), params)
    return [
        {
            "id": r.id,
            "event_type": r.event_type,
            "data": r.data if isinstance(r.data, dict) else json.loads(r.data or "{}"),
            "created_at": r.created_at.isoformat(),
        }
        for r in rows.fetchall()
    ]
