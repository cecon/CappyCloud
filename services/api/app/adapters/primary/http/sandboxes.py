"""Sandboxes HTTP router — lista e gerencia instâncias sandbox."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import get_authenticated_user, get_db_session
from app.domain.entities import User
from app.infrastructure.orm_models import Sandbox
from app.schemas import SandboxOut

router = APIRouter(prefix="/sandboxes", tags=["sandboxes"])


@router.get("", response_model=list[SandboxOut])
async def list_sandboxes(
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[SandboxOut]:
    """Lista todas as instâncias sandbox registadas."""
    rows = await session.execute(select(Sandbox).order_by(Sandbox.created_at))
    return [SandboxOut.model_validate(r) for r in rows.scalars()]


@router.patch("/{sandbox_id}/status", response_model=SandboxOut)
async def update_sandbox_status(
    sandbox_id: str,
    status: str,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SandboxOut:
    """Atualiza status de um sandbox (active | draining | offline)."""
    if status not in ("active", "draining", "offline"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="status deve ser active, draining ou offline")
    await session.execute(
        update(Sandbox).where(Sandbox.id == sandbox_id).values(status=status)
    )
    await session.commit()
    row = await session.get(Sandbox, sandbox_id)
    return SandboxOut.model_validate(row)
