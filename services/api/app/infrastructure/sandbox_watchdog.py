"""Watchdog que sincroniza mudanças do DB para a VM sandbox.

Roda a cada 10 s via APScheduler. Pega itens pending/error da sandbox_sync_queue,
executa a operação via HTTP na session_server.js e marca done/error.

Operações suportadas:
  clone_repo       → POST /repos/clone
  remove_repo      → DELETE /repos/:slug
  materialize_repo_graph → persiste /repos/:slug/graph em graph_nodes/graph_edges
  reconcile_repo_graph → resolve ref:* Roslyn em nós table/column
  update_git_auth  → POST /git-auth
  reconfigure_mcp  → POST /mcp/configure  (escreve ~/.claude/settings.json)
  reconfigure_model → ignorado por ora (configuração via env no openclaude)
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.secondary.sandbox_repo_graph_provider import SandboxRepositoryGraphProvider
from app.application.use_cases.repository_graph_doc_import import (
    materialize_doc_import,
    resolve_doc_import_commit_sha,
)
from app.application.use_cases.repository_graph_materialization import (
    materialize_repo_graph,
    resolve_repo_graph_commit_sha,
)
from app.application.use_cases.repository_graph_reconciliation import reconcile_repo_graph
from app.infrastructure.orm_models import Document, Repository, Sandbox, SandboxSyncQueue

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
                if item.operation == "materialize_repo_graph":
                    await self._materialize_repo_graph(session, sandbox, item.payload)
                elif item.operation == "doc_import_for_document":
                    await self._doc_import_for_document(session, sandbox, item.payload)
                elif item.operation == "reconcile_repo_graph":
                    await self._reconcile_repo_graph(session, item.payload)
                else:
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

            elif operation == "reconfigure_mcp":
                # payload: {"mcpServers": {...}} no formato do openclaude
                r = await client.post(f"{base}/mcp/configure", json=payload)
                r.raise_for_status()
                log.info("[watchdog] MCP reconfigured on sandbox %s", sandbox.name)

            else:
                raise ValueError(f"operação desconhecida: {operation}")

    async def _materialize_repo_graph(
        self,
        session: AsyncSession,
        sandbox: Sandbox,
        payload: dict[str, Any],
    ) -> None:
        repo_id = uuid.UUID(str(payload.get("repo_id") or ""))
        repo = await session.get(Repository, repo_id)
        if repo is None:
            raise ValueError("repositório não encontrado para materialização")
        commit_sha = str(payload.get("commit_sha") or "").strip()
        provider = SandboxRepositoryGraphProvider()
        if not commit_sha:
            commit_sha = await resolve_repo_graph_commit_sha(
                provider=provider,
                repo=repo,
                sandbox=sandbox,
            )
        max_files = max(50, min(int(payload.get("max_files") or 1200), 5000))
        async with session.begin_nested():
            await materialize_repo_graph(
                session,
                repo=repo,
                commit_sha=commit_sha,
                max_files=max_files,
                provider=provider,
            )

    async def _doc_import_for_document(
        self,
        session: AsyncSession,
        sandbox: Sandbox,
        payload: dict[str, Any],
    ) -> None:
        repo_id = uuid.UUID(str(payload.get("repo_id") or ""))
        document_id = uuid.UUID(str(payload.get("document_id") or ""))
        repo = await session.get(Repository, repo_id)
        document = await session.get(Document, document_id)
        if repo is None or document is None or document.repository_id != repo.id:
            raise ValueError("documento/repositório inválido para doc_import")
        commit_sha = str(payload.get("commit_sha") or "").strip()
        if not commit_sha:
            commit_sha = await resolve_doc_import_commit_sha(
                session=session,
                repo=repo,
                sandbox=sandbox,
            )
        async with session.begin_nested():
            await materialize_doc_import(
                session,
                repo=repo,
                commit_sha=commit_sha,
                document_ids=[document.id],
            )

    async def _reconcile_repo_graph(
        self,
        session: AsyncSession,
        payload: dict[str, Any],
    ) -> None:
        repo_id = uuid.UUID(str(payload.get("repo_id") or ""))
        repo = await session.get(Repository, repo_id)
        if repo is None:
            raise ValueError("repositório não encontrado para reconciliação")
        commit_sha = str(payload.get("commit_sha") or "").strip()
        if not commit_sha:
            raise ValueError("commit_sha obrigatório para reconciliação")
        async with session.begin_nested():
            await reconcile_repo_graph(
                session,
                repo=repo,
                commit_sha=commit_sha,
                mode=str(payload.get("mode") or "all"),
                llm_model=str(payload.get("llm_model") or "").strip() or None,
            )
