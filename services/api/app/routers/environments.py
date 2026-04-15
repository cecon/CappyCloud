"""Gestão do ciclo de vida do ambiente (sandbox container) por utilizador."""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.deps import get_current_user
from app.models import User

router = APIRouter(prefix="/environments", tags=["environments"])


@router.get("/status")
async def get_environment_status(
    request: Request,
    current: Annotated[User, Depends(get_current_user)],
) -> dict:
    """
    Retorna o estado atual do ambiente Docker do utilizador.

    Possíveis valores de ``status``:
    - ``none``     — sem registo nem container
    - ``stopped``  — container existe mas está parado (exited)
    - ``starting`` — a ser criado ou reiniciado
    - ``running``  — container a correr, gRPC acessível
    """
    pipeline = request.app.state.pipeline
    user_id = str(current.id)
    result = await asyncio.get_event_loop().run_in_executor(
        None, pipeline.get_env_status, user_id
    )
    return result


@router.post("/wake")
async def wake_environment(
    request: Request,
    current: Annotated[User, Depends(get_current_user)],
) -> dict:
    """
    Dispara a criação ou reinício do ambiente em background (fire-and-forget).

    Retorna imediatamente com ``{ "status": "starting" }``.
    O cliente deve fazer polling em ``GET /environments/status`` até receber ``running``.
    """
    pipeline = request.app.state.pipeline
    user_id = str(current.id)
    pipeline.wake_env(user_id)
    return {"status": "starting"}
