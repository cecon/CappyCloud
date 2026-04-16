"""
Environment Manager: manages per-conversation git worktrees inside the single
fixed sandbox container (cappycloud-sandbox).

Architecture (single fixed container):
  • One Docker container (cappycloud-sandbox) always running as a compose service.
  • Container hosts the git repo at /repos/default/ and the openclaude gRPC server.
  • Each conversation gets its own git worktree at /repos/default/sessions/<id>/.
  • ChatRequest.working_directory is set to the worktree path.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import docker
import docker.errors
import httpx

from ._session_store import SandboxRecord, SessionStore

log = logging.getLogger(__name__)


class EnvironmentManager:
    """Manages per-conversation worktrees inside the fixed sandbox container."""

    def __init__(
        self,
        session_store: SessionStore,
        sandbox_host: str,
        sandbox_grpc_port: int,
        sandbox_container_name: str = "cappycloud-sandbox",
        git_auth_token: str = "",
        code_indexer_url: str = "",
    ) -> None:
        self._store = session_store
        self._host = sandbox_host
        self._grpc_port = sandbox_grpc_port
        self._container_name = sandbox_container_name
        self._git_auth_token = git_auth_token
        self._code_indexer_url = code_indexer_url.rstrip("/")
        self._client = docker.from_env()
        self._container_id: Optional[str] = None

    # ── Startup ──────────────────────────────────────────────────

    def resolve_container(self) -> None:
        """Resolve and cache the fixed sandbox container ID.

        Called once at pipeline startup. Logs a warning if the container is
        not yet running (it may still be starting up).
        """
        try:
            container = self._client.containers.get(self._container_name)
            self._container_id = container.id
            log.info(
                "Sandbox container resolved: %s (%s)",
                self._container_name,
                container.id[:12],
            )
        except docker.errors.NotFound:
            log.warning(
                "Sandbox container %r not found at startup — "
                "docker exec calls will retry on demand.",
                self._container_name,
            )

    # ── Public API ───────────────────────────────────────────────

    async def get_or_create_session(
        self,
        user_id: str,
        chat_id: str,
        base_branch: str = "",
    ) -> SandboxRecord:
        """Return a SandboxRecord for the conversation, creating a git worktree if needed."""
        record = await self._store.get(user_id, chat_id)
        if record:
            if await self._worktree_exists(record.worktree_path):
                await self._store.refresh_ttl(user_id, chat_id)
                return record
            log.warning(
                "Worktree %s for %s/%s gone — recreating",
                record.worktree_path,
                user_id,
                chat_id,
            )
            await self._store.delete(user_id, chat_id)

        return await self._create_worktree_session(user_id, chat_id, base_branch)

    async def destroy_session(self, user_id: str, chat_id: str) -> None:
        """Remove the worktree for a session."""
        record = await self._store.get(user_id, chat_id)
        if not record:
            return

        if record.worktree_path:
            container = self._get_container()
            if container:
                try:
                    container.exec_run(
                        ["bash", "-c", f"rm -rf {record.worktree_path}"]
                    )
                    container.exec_run(
                        ["git", "-C", "/repos/default", "worktree", "prune"]
                    )
                    log.info(
                        "Removed worktree %s for %s/%s",
                        record.worktree_path,
                        user_id,
                        chat_id,
                    )
                except Exception as exc:
                    log.error("Error removing worktree: %s", exc)

        await self._store.delete(user_id, chat_id)

    async def gc_expired(self) -> None:
        """Destroy worktrees whose idle TTL has expired."""
        expired = await self._store.list_expired_sessions()
        for row in expired:
            await self.destroy_session(row["user_id"], row["chat_id"])

    # ── Internal ─────────────────────────────────────────────────

    async def _create_worktree_session(
        self,
        user_id: str,
        chat_id: str,
        base_branch: str = "main",
    ) -> SandboxRecord:
        """Create a git worktree for a new conversation and return its SandboxRecord."""
        session_id = chat_id.replace("-", "")[:16]
        worktree_path = f"/repos/default/sessions/{session_id}"

        log.info(
            "Creating worktree %r for %s/%s (base_branch=%s)",
            worktree_path,
            user_id,
            chat_id,
            base_branch,
        )

        container = self._get_container()
        if container is None:
            raise RuntimeError(
                f"Sandbox container {self._container_name!r} is not running. "
                "Check `docker compose ps` and inspect container logs."
            )

        try:
            exit_code, output = container.exec_run(
                ["/session_start.sh", "default", session_id, worktree_path, base_branch or "main"],
            )
            output_str = output.decode("utf-8", errors="replace") if output else ""
            if exit_code != 0:
                raise RuntimeError(
                    f"session_start.sh failed (exit {exit_code}): {output_str}"
                )
            log.debug("session_start.sh output: %s", output_str.strip())
        except docker.errors.NotFound:
            raise RuntimeError(
                f"Sandbox container {self._container_name!r} disappeared unexpectedly."
            )

        record = SandboxRecord(
            user_id=user_id,
            chat_id=chat_id,
            env_slug="default",
            container_id=container.id,
            grpc_host=self._host,
            grpc_port=self._grpc_port,
            worktree_path=worktree_path,
        )
        await self._store.save(record)

        asyncio.create_task(self._trigger_indexing())
        return record

    async def _trigger_indexing(self) -> None:
        """Fire-and-forget indexing request to the code-indexer service."""
        if not self._code_indexer_url or not self._container_id:
            return
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"{self._code_indexer_url}/index",
                    json={
                        "user_id": "default",
                        "container_id": self._container_id,
                        "workspace_path": "/repos/default",
                    },
                )
            log.info("Indexing triggered for default sandbox")
        except Exception as exc:
            log.warning("Failed to trigger indexing: %s", exc)

    def _get_container(self) -> Optional[docker.models.containers.Container]:
        """Return the sandbox container, resolving it if not yet cached."""
        try:
            container = self._client.containers.get(self._container_name)
            self._container_id = container.id
            return container
        except docker.errors.NotFound:
            log.error("Sandbox container %r not found", self._container_name)
            return None

    async def _worktree_exists(self, worktree_path: str) -> bool:
        """Check whether a worktree directory exists inside the sandbox container."""
        if not worktree_path:
            return False
        container = self._get_container()
        if container is None:
            return False
        try:
            exit_code, _ = container.exec_run(
                ["test", "-e", f"{worktree_path}/.git"],
            )
            return exit_code == 0
        except Exception as exc:
            log.debug("_worktree_exists check failed: %s", exc)
            return False
