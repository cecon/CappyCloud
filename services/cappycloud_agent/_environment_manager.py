"""
Environment Manager: manages per-conversation sessions inside sandbox containers.

Architecture:
  • One or more sandbox containers, each running an openclaude gRPC server and
    a session_server HTTP sidecar.
  • Each conversation gets a session_root directory with one git worktree per
    selected repo: /repos/sessions/<session_id>/<alias>/
  • Sandbox is selected by sandbox_id (stored on the Conversation).
  • No Docker socket needed — all worktree operations go through session_server HTTP.

session_server API:
  POST   /sessions                          → create session_root + worktrees (idempotent)
  DELETE /sessions/:id?session_root=&repos= → remove session_root
  GET    /health                            → liveness probe
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import httpx

from ._session_store import SandboxRecord, SessionStore

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SessionLease:
    """Resultado da preparação da sessão no sandbox."""

    record: SandboxRecord
    created: bool


class EnvironmentManager:
    """Manages per-conversation sessions inside sandbox containers."""

    def __init__(
        self,
        session_store: SessionStore,
        sandbox_host: str,
        sandbox_grpc_port: int,
        sandbox_session_port: int = 8080,
        sandbox_name: str = "cappycloud-sandbox",
    ) -> None:
        self._store = session_store
        self._default_host = sandbox_host
        self._default_grpc_port = sandbox_grpc_port
        self._default_session_port = sandbox_session_port
        self._default_name = sandbox_name

    def _session_base(self, host: str, session_port: int) -> str:
        return f"http://{host}:{session_port}"

    # ── Public API ───────────────────────────────────────────────

    async def get_or_create_session(
        self,
        user_id: str,
        chat_id: str,
        repos: list[dict] | None = None,
        session_root: str = "",
        sandbox_id: str = "",
    ) -> SessionLease:
        """Return (or create) a SandboxRecord for the conversation.

        session_server.js is idempotent: if session_root already exists it
        returns 200 immediately, so we call create on every request.
        """
        record = await self._store.get(user_id, chat_id)
        if record:
            await self._store.refresh_ttl(user_id, chat_id)
            await self._ensure_session(record)
            return SessionLease(record=record, created=False)

        return SessionLease(
            record=await self._create_session(
                user_id=user_id,
                chat_id=chat_id,
                repos=repos,
                session_root=session_root,
                sandbox_id=sandbox_id,
            ),
            created=True,
        )

    async def destroy_session(self, user_id: str, chat_id: str) -> None:
        record = await self._store.get(user_id, chat_id)
        if not record:
            return

        host = record.grpc_host or self._default_host
        base = self._session_base(host, self._default_session_port)
        session_id = record.chat_id.replace("-", "")[:12]

        if record.session_root:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    await client.delete(
                        f"{base}/sessions/{session_id}",
                        params={
                            "session_root": record.session_root,
                            "repos": json.dumps(record.repos),
                        },
                    )
                log.info("Removed session %s for %s/%s", session_id, user_id, chat_id)
            except Exception as exc:
                log.error("Error removing session via session server: %s", exc)

        await self._store.delete(user_id, chat_id)

    async def gc_expired(self) -> None:
        for row in await self._store.list_expired_sessions():
            await self.destroy_session(row["user_id"], row["chat_id"])

    # ── Internal ─────────────────────────────────────────────────

    async def _ensure_session(self, record: SandboxRecord) -> None:
        """Re-create worktrees if the volume was wiped (idempotent)."""
        host = record.grpc_host or self._default_host
        base = self._session_base(host, self._default_session_port)
        session_id = record.chat_id.replace("-", "")[:12]
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{base}/sessions",
                json=self._session_payload(
                    session_id, record.repos, record.session_root
                ),
            )
        if resp.status_code != 200:
            raise RuntimeError(
                f"session_server returned {resp.status_code}: {resp.text}"
            )

    async def _create_session(
        self,
        user_id: str,
        chat_id: str,
        repos: list[dict] | None,
        session_root: str,
        sandbox_id: str,
    ) -> SandboxRecord:
        session_id = chat_id.replace("-", "")[:12]

        host = self._default_host
        grpc_port = self._default_grpc_port
        base = self._session_base(host, self._default_session_port)

        session_root = session_root or f"/repos/sessions/{session_id}"
        resolved_repos = repos or []

        log.info(
            "Creating session %s for %s/%s (repos=%d, session_root=%r)",
            session_id,
            user_id,
            chat_id,
            len(resolved_repos),
            session_root,
        )

        payload = self._session_payload(session_id, resolved_repos, session_root)

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(f"{base}/sessions", json=payload)
            if resp.status_code != 200:
                raise RuntimeError(
                    f"session_server returned {resp.status_code}: {resp.text}"
                )
            resp_data = resp.json()
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"Cannot reach sandbox session server at {base}. "
                "Check if cappycloud-sandbox is running."
            ) from exc

        # Mescla branch_name retornado pelo session_server nos repos persistidos.
        repos_created: list[dict] = resp_data.get("repos_created") or []
        if repos_created:
            by_alias = {r["alias"]: r for r in repos_created if "alias" in r}
            for repo in resolved_repos:
                alias = repo.get("alias") or repo.get("slug", "")
                created = by_alias.get(alias)
                if created and not repo.get("branch_name"):
                    repo["branch_name"] = created["branch_name"]
                if created and not repo.get("worktree_path"):
                    repo["worktree_path"] = created["worktree_path"]

        record = SandboxRecord(
            user_id=user_id,
            chat_id=chat_id,
            sandbox_id=sandbox_id,
            sandbox_name=self._default_name,
            grpc_host=host,
            grpc_port=grpc_port,
            session_root=session_root,
            repos=resolved_repos,
        )
        await self._store.save(record)
        return record

    @staticmethod
    def _session_payload(
        session_id: str,
        repos: list[dict],
        session_root: str,
    ) -> dict:
        return {
            "session_id": session_id,
            "repos": repos,
            "session_root": session_root,
        }
