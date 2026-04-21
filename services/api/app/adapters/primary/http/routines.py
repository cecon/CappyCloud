"""HTTP adapter for Routines — CRUD, manual trigger and run history."""

from __future__ import annotations

import json
import logging
import uuid as _uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http._routines_scheduler import (
    register_routine_schedules,
    unregister_routine_schedules,
)
from app.adapters.primary.http.deps import get_authenticated_user, get_db_session
from app.domain.entities import User

log = logging.getLogger(__name__)

router = APIRouter(prefix="/routines", tags=["routines"])


class TriggerConfig(BaseModel):
    type: str = Field(description="schedule | api | github")
    config: dict = Field(default_factory=dict)


class RoutineIn(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    prompt: str = Field(min_length=1)
    env_slug: str = Field(min_length=1, max_length=128)
    triggers: list[TriggerConfig] = Field(default_factory=list)
    enabled: bool = True


class RoutineOut(BaseModel):
    id: str
    name: str
    prompt: str
    env_slug: str
    triggers: list[dict]
    enabled: bool
    created_at: str
    last_run_at: str | None


def _row_to_out(r) -> RoutineOut:
    return RoutineOut(
        id=str(r.id),
        name=r.name,
        prompt=r.prompt,
        env_slug=r.env_slug,
        triggers=r.triggers if isinstance(r.triggers, list) else json.loads(r.triggers or "[]"),
        enabled=r.enabled,
        created_at=r.created_at.isoformat(),
        last_run_at=r.last_run_at.isoformat() if r.last_run_at else None,
    )


@router.get("", response_model=list[RoutineOut])
async def list_routines(
    current: Annotated[User, Depends(get_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[RoutineOut]:
    rows = await db.execute(
        text(
            "SELECT id, name, prompt, env_slug, triggers, enabled, created_at, last_run_at "
            "FROM routines WHERE created_by = :uid ORDER BY created_at DESC"
        ),
        {"uid": str(current.id)},
    )
    return [_row_to_out(r) for r in rows.fetchall()]


@router.post("", response_model=RoutineOut, status_code=status.HTTP_201_CREATED)
async def create_routine(
    body: RoutineIn,
    current: Annotated[User, Depends(get_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    request: Request,
) -> RoutineOut:
    rid = str(_uuid.uuid4())
    triggers_json = json.dumps([t.model_dump() for t in body.triggers])
    await db.execute(
        text(
            "INSERT INTO routines (id, name, prompt, env_slug, triggers, enabled, created_by) "
            "VALUES (:id, :name, :prompt, :slug, :triggers::jsonb, :enabled, :uid)"
        ),
        {
            "id": rid,
            "name": body.name,
            "prompt": body.prompt,
            "slug": body.env_slug,
            "triggers": triggers_json,
            "enabled": body.enabled,
            "uid": str(current.id),
        },
    )
    await db.commit()
    register_routine_schedules(request, rid, body)
    row = await db.execute(
        text(
            "SELECT id, name, prompt, env_slug, triggers, enabled, created_at, last_run_at "
            "FROM routines WHERE id = :id"
        ),
        {"id": rid},
    )
    return _row_to_out(row.fetchone())


@router.get("/{routine_id}", response_model=RoutineOut)
async def get_routine(
    routine_id: str,
    current: Annotated[User, Depends(get_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> RoutineOut:
    row = await db.execute(
        text(
            "SELECT id, name, prompt, env_slug, triggers, enabled, created_at, last_run_at "
            "FROM routines WHERE id = :id AND created_by = :uid"
        ),
        {"id": routine_id, "uid": str(current.id)},
    )
    r = row.fetchone()
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Routine não encontrada.")
    return _row_to_out(r)


@router.put("/{routine_id}", response_model=RoutineOut)
async def update_routine(
    routine_id: str,
    body: RoutineIn,
    current: Annotated[User, Depends(get_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    request: Request,
) -> RoutineOut:
    triggers_json = json.dumps([t.model_dump() for t in body.triggers])
    result = await db.execute(
        text(
            "UPDATE routines SET name=:name, prompt=:prompt, env_slug=:slug, "
            "triggers=:triggers::jsonb, enabled=:enabled "
            "WHERE id=:id AND created_by=:uid RETURNING id"
        ),
        {
            "id": routine_id,
            "uid": str(current.id),
            "name": body.name,
            "prompt": body.prompt,
            "slug": body.env_slug,
            "triggers": triggers_json,
            "enabled": body.enabled,
        },
    )
    if not result.fetchone():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Routine não encontrada.")
    await db.commit()
    unregister_routine_schedules(request, routine_id)
    register_routine_schedules(request, routine_id, body)
    return await get_routine(routine_id, current, db)


@router.delete("/{routine_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_routine(
    routine_id: str,
    current: Annotated[User, Depends(get_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    request: Request,
) -> None:
    result = await db.execute(
        text("DELETE FROM routines WHERE id=:id AND created_by=:uid RETURNING id"),
        {"id": routine_id, "uid": str(current.id)},
    )
    if not result.fetchone():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Routine não encontrada.")
    await db.commit()
    unregister_routine_schedules(request, routine_id)


@router.post("/{routine_id}/run")
async def run_routine(
    routine_id: str,
    current: Annotated[User, Depends(get_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    request: Request,
) -> dict:
    return await _fire_routine(routine_id, "manual", db, request)


@router.post("/{routine_id}/fire")
async def fire_routine_api(
    routine_id: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Disparo por API token (Bearer) — não requer sessão de utilizador."""
    import hashlib

    auth = request.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token em falta.")

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    row = await db.execute(
        text(
            "SELECT id FROM routines WHERE id = :rid AND api_token_hash = :hash AND enabled = TRUE"
        ),
        {"rid": routine_id, "hash": token_hash},
    )
    if not row.fetchone():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token inválido ou routine inativa.",
        )
    return await _fire_routine(routine_id, "api", db, request)


@router.get("/{routine_id}/runs")
async def list_routine_runs(
    routine_id: str,
    current: Annotated[User, Depends(get_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[dict]:
    row = await db.execute(
        text("SELECT id FROM routines WHERE id = :rid AND created_by = :uid"),
        {"rid": routine_id, "uid": str(current.id)},
    )
    if not row.fetchone():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Routine não encontrada.")

    runs = await db.execute(
        text(
            "SELECT id, task_id, triggered_by, status, started_at "
            "FROM routine_runs WHERE routine_id = :rid ORDER BY started_at DESC LIMIT 50"
        ),
        {"rid": routine_id},
    )
    return [
        {
            "id": str(r.id),
            "task_id": str(r.task_id) if r.task_id else None,
            "triggered_by": r.triggered_by,
            "status": r.status,
            "started_at": r.started_at.isoformat(),
        }
        for r in runs.fetchall()
    ]


async def _fire_routine(
    routine_id: str,
    triggered_by: str,
    db: AsyncSession,
    request: Request,
) -> dict:
    row = await db.execute(
        text("SELECT id, prompt, env_slug, enabled FROM routines WHERE id = :rid"),
        {"rid": routine_id},
    )
    r = row.fetchone()
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Routine não encontrada.")
    if not r.enabled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Routine desativada.")

    task_id: str | None = None
    try:
        agent = request.app.state.agent
        task_id = await agent.dispatch(
            prompt=r.prompt,
            triggered_by=triggered_by,
            trigger_payload={"routine_id": routine_id, "triggered_by": triggered_by},
        )
    except Exception as exc:
        log.error("Routine %s dispatch failed: %s", routine_id, exc)

    run_id = str(_uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO routine_runs (id, routine_id, task_id, triggered_by, status) "
            "VALUES (:id, :rid, :tid::uuid, :tby, 'pending')"
        ),
        {"id": run_id, "rid": routine_id, "tid": task_id, "tby": triggered_by},
    )
    await db.execute(
        text("UPDATE routines SET last_run_at = NOW() WHERE id = :rid"),
        {"rid": routine_id},
    )
    await db.commit()
    return {"run_id": run_id, "task_id": task_id, "routine_id": routine_id}
