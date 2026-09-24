"""Guarda HTTP para impedir chat em sandbox indisponivel."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.value_objects import AgentRuntime, is_claude_cli_model
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


async def uses_claude_cli_model(
    session: AsyncSession, sandbox_id: uuid.UUID | None, model_id: str | None
) -> bool:
    """True se ``model_id`` é um modelo do Claude CLI e a sandbox roda o Claude CLI.

    Esses modelos não estão no catálogo: valem só onde o Claude CLI responde.
    """
    if not is_claude_cli_model(model_id):
        return False
    sandbox = await session.get(Sandbox, sandbox_id) if sandbox_id else None
    if sandbox is None or sandbox.agent_runtime != AgentRuntime.CLAUDE_CLI.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Modelos do Claude CLI só valem em sandbox com o runtime Claude CLI.",
        )
    return True
