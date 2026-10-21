"""Terminal web da sandbox (super admin), ex.: para o ``claude login``.

Repassa para o ``terminal_handler.js`` do session server da sandbox, que roda
um shell num pseudo-terminal. A saída vem em NDJSON (base64) e a entrada vai
por POST — sem WebSocket, igual ao streaming do chat.
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from collections.abc import AsyncIterator
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.adapters.primary.http.admin_sandboxes import get_sandbox_repo
from app.adapters.primary.http.deps_auth import require_super_admin
from app.application.use_cases.admin_sandboxes import GetSandbox, SandboxNotFoundError
from app.domain.entities import Sandbox, User
from app.ports.repositories import SandboxRepository

log = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/sandboxes", tags=["admin"])

_TERMINAL_ID = re.compile(r"^[a-f0-9]{32}$")


class TerminalSize(BaseModel):
    cols: int = Field(default=120, ge=20, le=500)
    rows: int = Field(default=32, ge=5, le=200)


class TerminalInput(BaseModel):
    data: str = Field(max_length=65536)


async def _sandbox(sandbox_id: uuid.UUID, repo: SandboxRepository) -> Sandbox:
    try:
        return await GetSandbox(repo).execute(sandbox_id)
    except SandboxNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _url(sb: Sandbox, terminal_id: str | None = None, action: str = "") -> str:
    path = "/terminal/sessions"
    if terminal_id is not None:
        if not _TERMINAL_ID.match(terminal_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Terminal inválido.")
        path += f"/{terminal_id}" + (f"/{action}" if action else "")
    return f"http://{sb.host}:{sb.session_port}{path}"


def _headers() -> dict[str, str]:
    return {"X-Internal-Token": os.getenv("INTERNAL_API_TOKEN", "").strip()}


async def _call(method: str, url: str, body: dict[str, Any] | None = None) -> dict:
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.request(method, url, json=body, headers=_headers())
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Sandbox indisponível para o terminal: {exc}",
        ) from exc
    data = resp.json() if resp.content else {}
    if resp.status_code == 404 and "terminal" not in str(data.get("error", "")).lower():
        detail = "A imagem desta sandbox ainda não tem terminal; atualize a sandbox."
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=data.get("error") or resp.text)
    return data


@router.post("/{sandbox_id}/terminal")
async def open_terminal(
    sandbox_id: uuid.UUID,
    size: TerminalSize,
    current: Annotated[User, Depends(require_super_admin)],
    repo: Annotated[SandboxRepository, Depends(get_sandbox_repo)],
) -> dict:
    """Abre um shell na sandbox. Fica registrado quem abriu."""
    sb = await _sandbox(sandbox_id, repo)
    data = await _call("POST", _url(sb), size.model_dump())
    log.warning(
        "terminal da sandbox %s (%s) aberto por %s: %s",
        sb.name,
        sb.id,
        current.email,
        data.get("id"),
    )
    return {"id": data.get("id")}


@router.get("/{sandbox_id}/terminal/{terminal_id}/stream")
async def stream_terminal(
    sandbox_id: uuid.UUID,
    terminal_id: str,
    _current: Annotated[User, Depends(require_super_admin)],
    repo: Annotated[SandboxRepository, Depends(get_sandbox_repo)],
) -> StreamingResponse:
    """Saída do shell em NDJSON: ``{"type": "output", "data": <base64>}`` / ``exit``."""
    url = _url(await _sandbox(sandbox_id, repo), terminal_id, "stream")

    async def relay() -> AsyncIterator[bytes]:
        timeout = httpx.Timeout(10, read=None)
        try:
            async with (
                httpx.AsyncClient(timeout=timeout) as http,
                http.stream("GET", url, headers=_headers()) as resp,
            ):
                if resp.status_code >= 400:
                    yield b'{"type": "exit", "code": -1, "error": "terminal encerrado"}\n'
                    return
                async for chunk in resp.aiter_bytes():
                    yield chunk
        except httpx.HTTPError as exc:
            log.info("stream do terminal %s interrompido: %s", terminal_id, exc)

    return StreamingResponse(
        relay(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.post("/{sandbox_id}/terminal/{terminal_id}/input")
async def terminal_input(
    sandbox_id: uuid.UUID,
    terminal_id: str,
    body: TerminalInput,
    _current: Annotated[User, Depends(require_super_admin)],
    repo: Annotated[SandboxRepository, Depends(get_sandbox_repo)],
) -> dict:
    sb = await _sandbox(sandbox_id, repo)
    return await _call("POST", _url(sb, terminal_id, "input"), body.model_dump())


@router.post("/{sandbox_id}/terminal/{terminal_id}/resize")
async def terminal_resize(
    sandbox_id: uuid.UUID,
    terminal_id: str,
    size: TerminalSize,
    _current: Annotated[User, Depends(require_super_admin)],
    repo: Annotated[SandboxRepository, Depends(get_sandbox_repo)],
) -> dict:
    sb = await _sandbox(sandbox_id, repo)
    return await _call("POST", _url(sb, terminal_id, "resize"), size.model_dump())


@router.delete("/{sandbox_id}/terminal/{terminal_id}")
async def close_terminal(
    sandbox_id: uuid.UUID,
    terminal_id: str,
    _current: Annotated[User, Depends(require_super_admin)],
    repo: Annotated[SandboxRepository, Depends(get_sandbox_repo)],
) -> dict:
    sb = await _sandbox(sandbox_id, repo)
    return await _call("DELETE", _url(sb, terminal_id))
