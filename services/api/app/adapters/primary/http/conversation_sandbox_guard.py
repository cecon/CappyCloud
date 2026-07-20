"""Guarda HTTP para impedir chat em sandbox indisponivel."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.orm_models import Sandbox

_CHAT_READY_CONTAINER_STATUSES = frozenset({"running", "configured"})


async def ensure_sandbox_ready_for_chat(
    session: AsyncSession,
    sandbox_id: uuid.UUID,
) -> None:
    sandbox = await session.get(Sandbox, sandbox_id)
    if sandbox is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sandbox selecionada não encontrada.",
        )
    if sandbox.status == "active" and sandbox.container_status in _CHAT_READY_CONTAINER_STATUSES:
        return
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            f"Sandbox '{sandbox.name}' não está pronta para chat "
            f"(status={sandbox.container_status}). Inicie a sandbox antes de enviar."
        ),
    )
