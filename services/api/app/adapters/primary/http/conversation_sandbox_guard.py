"""Guarda HTTP para impedir chat em sandbox indisponivel."""

from __future__ import annotations

import logging
import uuid

import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.value_objects import AgentRuntime, is_claude_cli_model
from app.infrastructure.orm_models import Sandbox

log = logging.getLogger(__name__)

_CHAT_READY_CONTAINER_STATUSES = frozenset({"running", "configured"})


async def sandbox_answers(sandbox: Sandbox) -> bool:
    """True se o session_server da sandbox responde e o runtime do chat está de pé.

    O openclaude parado só conta quando é ele que atende o chat (runtime openclaude).
    """
    url = f"http://{sandbox.host}:{sandbox.session_port}/health"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(url)
        if response.status_code != 200:
            return False
        data = response.json()
    except httpx.HTTPError, ValueError:
        return False
    uses_openclaude = sandbox.agent_runtime != AgentRuntime.CLAUDE_CLI.value
    return not (uses_openclaude and isinstance(data, dict) and data.get("openclaude") == "stopped")


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
    # O container_status é gravado no boot e na listagem do admin, e fica velho: um
    # boot que falhou num deploy, ou uma checagem no meio de um reinício, deixava o
    # chat bloqueado para todos com a sandbox de pé. Antes de recusar, pergunta a ela.
    if sandbox.status == "active" and await sandbox_answers(sandbox):
        log.warning(
            "Sandbox %s estava %s mas responde: marcada como configured",
            sandbox.name,
            sandbox.container_status,
        )
        sandbox.container_status = "configured"
        await session.commit()
        return
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            f"Sandbox '{sandbox.name}' não está respondendo "
            f"(status={sandbox.container_status}). Peça a um admin para iniciá-la em "
            "Admin → Sandboxes."
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
