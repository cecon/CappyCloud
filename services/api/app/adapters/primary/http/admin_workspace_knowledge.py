"""Admin do conhecimento de um workspace (só super admin).

  GET  /admin/workspaces/{id}/knowledge            → status do grafo e arquivos
  GET  /admin/workspaces/{id}/knowledge/file?path= → um arquivo de knowledge/ ou memory/
  POST /admin/workspaces/{id}/knowledge/build      → enfileira a reconstrução ("Atualizar agora")
  GET  /admin/workspaces/{id}/knowledge/memories   → memórias do agentmemory deste workspace
  GET  /admin/workspaces/{id}/knowledge/summary    → selos da lista (grafo e memória)

Os dados vêm do sandbox do workspace (``knowledge_handler.js`` e ``memory_handler.js``).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import get_db_session
from app.adapters.primary.http.deps_auth import require_super_admin
from app.infrastructure.orm_models import Sandbox
from app.infrastructure.orm_models_workspaces import Workspace
from app.infrastructure.workspace_knowledge import enqueue_knowledge_build

router = APIRouter(
    prefix="/admin/workspaces/{workspace_id}/knowledge",
    tags=["admin"],
    dependencies=[Depends(require_super_admin)],
)

Session = Annotated[AsyncSession, Depends(get_db_session)]
SandboxGet = Callable[[str, dict[str, str]], Awaitable[tuple[int, Any]]]


def get_sandbox_get() -> SandboxGet:
    """GET JSON num sandbox: devolve (status HTTP, corpo). 502 se não responder."""

    async def get(url: str, params: dict[str, str]) -> tuple[int, Any]:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(url, params=params)
            return response.status_code, response.json()
        except (httpx.HTTPError, ValueError) as exc:
            return 502, {"error": f"sandbox não respondeu: {exc}"}

    return get


SandboxGetter = Annotated[SandboxGet, Depends(get_sandbox_get)]


async def _workspace_url(session: AsyncSession, workspace_id: uuid.UUID) -> tuple[Workspace, str]:
    ws = await session.get(Workspace, workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace não encontrado.")
    sandbox = await session.get(Sandbox, ws.sandbox_id)
    if sandbox is None:
        raise HTTPException(status_code=409, detail="O sandbox do workspace não existe mais.")
    base = f"http://{sandbox.host}:{sandbox.session_port}/workspaces/{ws.slug}"
    return ws, base


def _reply(code: int, body: Any) -> Any:
    if code >= 400:
        detail = body.get("error") if isinstance(body, dict) else None
        raise HTTPException(status_code=502 if code >= 500 else 400, detail=detail or "erro")
    return body


@router.get("")
async def knowledge_overview(
    workspace_id: uuid.UUID, session: Session, sandbox_get: SandboxGetter
) -> Any:
    _, base = await _workspace_url(session, workspace_id)
    return _reply(*await sandbox_get(f"{base}/knowledge", {}))


@router.get("/file")
async def knowledge_file(
    workspace_id: uuid.UUID,
    session: Session,
    sandbox_get: SandboxGetter,
    path: Annotated[str, Query(min_length=1, max_length=512)],
) -> Any:
    _, base = await _workspace_url(session, workspace_id)
    return _reply(*await sandbox_get(f"{base}/knowledge/file", {"path": path}))


@router.post("/build", status_code=202)
async def knowledge_build(workspace_id: uuid.UUID, session: Session) -> dict:
    ws, _ = await _workspace_url(session, workspace_id)
    queued = await enqueue_knowledge_build(session, ws)
    await session.commit()
    return {"queued": queued}


@router.get("/memories")
async def knowledge_memories(
    workspace_id: uuid.UUID, session: Session, sandbox_get: SandboxGetter
) -> Any:
    _, base = await _workspace_url(session, workspace_id)
    return _reply(*await sandbox_get(f"{base}/memory", {}))


@router.get("/summary")
async def knowledge_summary(
    workspace_id: uuid.UUID, session: Session, sandbox_get: SandboxGetter
) -> dict:
    """Grafo (estado, commits novos desde a geração) e memória (total, última gravação).

    Nunca falha pela metade: o que o sandbox não responder vira ``available: false``.
    """
    _, base = await _workspace_url(session, workspace_id)
    graph_code, graph = await sandbox_get(f"{base}/knowledge/summary", {})
    memory_code, memory = await sandbox_get(f"{base}/memory", {})
    memories = memory.get("memories", []) if memory_code < 400 else []
    return {
        "graph": graph if graph_code < 400 else {"available": False, "error": graph.get("error")},
        "memory": {
            "available": memory_code < 400,
            "total": memory.get("total", 0) if memory_code < 400 else 0,
            "last_at": (memories[0].get("updated_at") or memories[0].get("created_at"))
            if memories
            else None,
            "error": None if memory_code < 400 else memory.get("error"),
        },
    }
