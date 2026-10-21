"""Grafo de código (graphify) dos workspaces: quando reconstruir.

A reconstrução roda no sandbox (``knowledge_handler.js``). A API só enfileira
``build_knowledge`` no ``sandbox_sync_queue``: depois de cada sincronização do
workspace, uma vez por dia e pelo botão "Atualizar agora" do admin. O watchdog
chama o sandbox, que responde na hora e reconstrói em segundo plano.
"""

from __future__ import annotations

import logging
import uuid

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.orm_models import SandboxSyncQueue
from app.infrastructure.orm_models_workspaces import Workspace

log = logging.getLogger(__name__)

OPERATION = "build_knowledge"


async def enqueue_knowledge_build(session: AsyncSession, ws: Workspace) -> bool:
    """Enfileira a reconstrução, a menos que já haja uma pendente para o workspace."""
    pending = await session.scalars(
        select(SandboxSyncQueue.payload)
        .where(SandboxSyncQueue.operation == OPERATION)
        .where(SandboxSyncQueue.sandbox_id == ws.sandbox_id)
        .where(SandboxSyncQueue.status.in_(["pending", "processing"]))
    )
    if any((payload or {}).get("slug") == ws.slug for payload in pending):
        return False
    session.add(
        SandboxSyncQueue(
            id=uuid.uuid4(),
            sandbox_id=ws.sandbox_id,
            operation=OPERATION,
            payload={"slug": ws.slug},
            priority=7,
        )
    )
    return True


async def enqueue_daily_builds(session_factory: async_sessionmaker) -> None:
    async with session_factory() as session:
        workspaces = (await session.scalars(select(Workspace).where(Workspace.active))).all()
        queued = [ws.slug for ws in workspaces if await enqueue_knowledge_build(session, ws)]
        await session.commit()
    log.info("[knowledge] reconstrução diária enfileirada: %s", ", ".join(queued) or "(nenhum)")


def register_knowledge_jobs(
    scheduler: AsyncIOScheduler, session_factory: async_sessionmaker
) -> None:
    scheduler.add_job(
        enqueue_daily_builds,
        "cron",
        hour=4,
        minute=10,
        id="workspace_knowledge_daily",
        replace_existing=True,
        kwargs={"session_factory": session_factory},
    )
