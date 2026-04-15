"""Environments HTTP adapter — thin glue for sandbox lifecycle endpoints.

Endpoints delegate to AgentPort; no business logic lives here.
"""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends

from app.adapters.primary.http.deps import get_agent, get_authenticated_user
from app.domain.entities import User
from app.ports.agent import AgentPort

router = APIRouter(prefix="/environments", tags=["environments"])


@router.get("/status")
async def get_environment_status(
    current: Annotated[User, Depends(get_authenticated_user)],
    agent: Annotated[AgentPort, Depends(get_agent)],
) -> dict:  # type: ignore[type-arg]
    """Return the current status of the user's sandbox environment.

    Possible ``status`` values: ``none``, ``stopped``, ``starting``, ``running``.
    """
    return await asyncio.get_event_loop().run_in_executor(
        None, agent.get_env_status, str(current.id)
    )


@router.post("/wake")
async def wake_environment(
    current: Annotated[User, Depends(get_authenticated_user)],
    agent: Annotated[AgentPort, Depends(get_agent)],
) -> dict:  # type: ignore[type-arg]
    """Trigger sandbox environment creation/restart (fire-and-forget).

    Returns immediately. Poll ``GET /environments/status`` until ``running``.
    """
    agent.wake_env(str(current.id))
    return {"status": "starting"}
