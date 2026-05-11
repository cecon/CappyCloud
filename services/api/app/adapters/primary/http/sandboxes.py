"""Sandboxes HTTP router — lista e gerencia instâncias sandbox."""

from __future__ import annotations

import os
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import get_authenticated_user, get_db_session
from app.domain.entities import User
from app.infrastructure.orm_models import Sandbox
from app.schemas import SandboxOut, SandboxRegister

router = APIRouter(prefix="/sandboxes", tags=["sandboxes"])


@router.get("", response_model=list[SandboxOut])
async def list_sandboxes(
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[SandboxOut]:
    """Lista todas as instâncias sandbox registadas."""
    rows = await session.execute(select(Sandbox).order_by(Sandbox.created_at))
    return [SandboxOut.model_validate(r) for r in rows.scalars()]


@router.post("/register", response_model=SandboxOut, status_code=status.HTTP_200_OK)
async def register_sandbox(
    body: SandboxRegister,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SandboxOut:
    """Auto-registro de container sandbox.

    O container chama este endpoint no startup passando ``register_token``
    configurado via env var ``SANDBOX_REGISTER_TOKEN``. Se o token bater,
    cria ou atualiza o registro de Sandbox com o host/portas atuais.
    """
    expected = os.environ.get("SANDBOX_REGISTER_TOKEN", "")
    if not expected or body.register_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido.")

    result = await session.execute(select(Sandbox).where(Sandbox.name == body.name))
    row = result.scalar_one_or_none()

    if row:
        row.host = body.host
        row.grpc_port = body.grpc_port
        row.session_port = body.session_port
        row.status = "active"
        row.register_token = body.register_token
    else:
        row = Sandbox(
            id=uuid.uuid4(),
            name=body.name,
            host=body.host,
            grpc_port=body.grpc_port,
            session_port=body.session_port,
            status="active",
            register_token=body.register_token,
        )
        session.add(row)

    await session.commit()
    await session.refresh(row)
    return SandboxOut.model_validate(row)


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
    await session.execute(update(Sandbox).where(Sandbox.id == sandbox_id).values(status=status))
    await session.commit()
    row = await session.get(Sandbox, sandbox_id)
    return SandboxOut.model_validate(row)
