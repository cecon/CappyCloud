"""Watchdog que sincroniza mudanças do DB para a VM sandbox.

Roda a cada 10 s via APScheduler. Pega itens pending/error da sandbox_sync_queue,
executa a operação via HTTP na session_server.js e marca done/error.

Operações suportadas:
  clone_repo      → POST /repos/clone
  remove_repo     → DELETE /repos/:slug
  update_git_auth → POST /git-auth
  reconfigure_model → ignorado por ora (configuração via env no openclaude)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.orm_models import Repository, Sandbox, SandboxSyncQueue

log = logging.getLogger(__name__)

_MAX_RETRIES = 3


class SandboxWatchdog:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = session_factory

    async def run_once(self) -> None:
        async with self._factory() as session:
            await self._process_pending(session)

    async def _process_pending(self, session: AsyncSession) -> None:
        rows = await session.execute(
            select(SandboxSyncQueue)
            .where(SandboxSyncQueue.status.in_(["pending", "error"]))
            .where(SandboxSyncQueue.retries < _MAX_RETRIES)
            .order_by(SandboxSyncQueue.priority, SandboxSyncQueue.created_at)
            .limit(20)
        )
        items: list[SandboxSyncQueue] = list(rows.scalars())
        if not items:
            return

        sandbox_cache: dict[str, Sandbox | None] = {}

        for item in items:
            key = str(item.sandbox_id)
            if key not in sandbox_cache:
                sandbox_cache[key] = await session.get(Sandbox, item.sandbox_id)
            sandbox = sandbox_cache[key]

            if not sandbox:
                item.status = "error"
                item.last_error = "sandbox not found in DB"
                continue

            item.status = "processing"
            await session.flush()

            try:
                await self._execute(sandbox, item.operation, item.payload)
                item.status = "done"
                item.last_error = None
                await self._sync_repo_state(session, item)
            except Exception as exc:
                item.retries += 1
                item.last_error = str(exc)
                item.status = "error" if item.retries >= _MAX_RETRIES else "pending"
                log.warning(
                    "[watchdog] %s failed (retry %d): %s", item.operation, item.retries, exc
                )
                await self._sync_repo_state(session, item, error=str(exc)[:500])

        await session.commit()

    async def _sync_repo_state(
        self,
        session: AsyncSession,
        item: SandboxSyncQueue,
        error: str | None = None,
    ) -> None:
        """Atualiza ``repositories.sandbox_status`` e ``last_sync_at`` após operação."""
        if item.operation not in {"clone_repo", "remove_repo"}:
            return
        slug = (item.payload or {}).get("slug", "")
        if not slug:
            return
        rows = await session.execute(select(Repository).where(Repository.slug == slug))
        repo = rows.scalar_one_or_none()
        if not repo:
            return
        if item.operation == "clone_repo":
            if error:
                repo.sandbox_status = "error"
                repo.error_message = error
            else:
                repo.sandbox_status = "cloned"
                repo.sandbox_path = f"/repos/{slug}"
                repo.last_sync_at = datetime.now(UTC)
                repo.error_message = None
        elif item.operation == "remove_repo" and not error:
            repo.sandbox_status = "not_cloned"
            repo.sandbox_path = ""
            repo.last_sync_at = datetime.now(UTC)

    async def _execute(self, sandbox: Sandbox, operation: str, payload: dict[str, Any]) -> None:
        base = f"http://{sandbox.host}:{sandbox.session_port}"

        async with httpx.AsyncClient(timeout=60) as client:
            if operation == "clone_repo":
                r = await client.post(f"{base}/repos/clone", json=payload)
                r.raise_for_status()

            elif operation == "remove_repo":
                slug = payload.get("slug", "")
                r = await client.delete(f"{base}/repos/{slug}", params=payload)
                r.raise_for_status()

            elif operation == "update_git_auth":
                r = await client.post(f"{base}/git-auth", json=payload)
                r.raise_for_status()

            elif operation == "reconfigure_model":
                log.info("[watchdog] reconfigure_model não implementado no session_server ainda")

            else:
                raise ValueError(f"operação desconhecida: {operation}")
