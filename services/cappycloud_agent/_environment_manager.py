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
from typing import Optional

import httpx

from ._session_store import SandboxRecord, SessionStore

log = logging.getLogger(__name__)


class EnvironmentManager:
    """Manages per-conversation sessions inside sandbox containers."""

    def __init__(
        self,
        session_store: SessionStore,
        sandbox_host: str,
        sandbox_grpc_port: int,
        sandbox_session_port: int = 8080,
        sandbox_name: str = "cappycloud-sandbox",
        # Legacy param — ignored, kept for call-site compat
        sandbox_container_name: str = "cappycloud-sandbox",
        git_auth_token: str = "",
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
        sandbox_id: str = "",
        # Legacy single-repo params (still supported)
        base_branch: str = "",
        repo_slug: str = "default",
        worktree_branch: str = "",
        worktree_path: str = "",
    ) -> SandboxRecord:
        """Return (or create) a SandboxRecord for the conversation.

        session_server.js is idempotent: if session_root already exists it
        returns 200 immediately, so we call create on every request.
        """
        record = await self._store.get(user_id, chat_id)
        if record:
            await self._store.refresh_ttl(user_id, chat_id)
            await self._ensure_session(record)
            return record

        return await self._create_session(
            user_id=user_id,
            chat_id=chat_id,
            repos=repos,
            sandbox_id=sandbox_id,
            base_branch=base_branch,
            repo_slug=repo_slug,
            worktree_branch=worktree_branch,
            worktree_path=worktree_path,
        )

    async def destroy_session(self, user_id: str, chat_id: str) -> None:
        record = await self._store.get(user_id, chat_id)
        if not record:
            return

        host = record.grpc_host or self._default_host
        base = self._session_base(host, self._default_session_port)
        session_id = record.chat_id.replace("-", "")[:12]

        if record.session_root or record.worktree_path:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    await client.delete(
                        f"{base}/sessions/{session_id}",
                        params={
                            "session_root": record.session_root,
                            "repos": json.dumps(record.repos),
                            "env_slug": record.env_slug,
                            "worktree_path": record.worktree_path,
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
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                await client.post(
                    f"{base}/sessions",
                    json=self._session_payload(session_id, record.repos, record.session_root,
                                               record.env_slug, record.worktree_path,
                                               record.worktree_path,
                                               f"cappy/{record.env_slug}/{session_id}"),
                )
        except Exception as exc:
            log.warning("_ensure_session non-fatal: %s", exc)

    async def _create_session(
        self,
        user_id: str,
        chat_id: str,
        repos: list[dict] | None,
        sandbox_id: str,
        base_branch: str,
        repo_slug: str,
        worktree_branch: str,
        worktree_path: str,
    ) -> SandboxRecord:
        session_id = chat_id.replace("-", "")[:12]

        # Resolve which sandbox to use (future: look up from DB by sandbox_id)
        host = self._default_host
        grpc_port = self._default_grpc_port
        base = self._session_base(host, self._default_session_port)

        # Build repos and session_root
        if repos:
            session_root = f"/repos/sessions/{session_id}"
            legacy_wt = ""
            legacy_slug = repos[0]["slug"] if repos else repo_slug
        else:
            # Legacy single-repo
            session_root = ""
            legacy_wt = worktree_path or f"/repos/{repo_slug}/sessions/{session_id}"
            legacy_slug = repo_slug
            repos = []

        log.info(
            "Creating session %s for %s/%s (repos=%d, session_root=%r)",
            session_id, user_id, chat_id, len(repos), session_root or legacy_wt,
        )

        payload = self._session_payload(
            session_id, repos, session_root,
            legacy_slug, legacy_wt, worktree_branch or f"cappy/{legacy_slug}/{session_id}",
            worktree_branch or f"cappy/{legacy_slug}/{session_id}",
        )

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(f"{base}/sessions", json=payload)
            if resp.status_code != 200:
                raise RuntimeError(
                    f"session_server returned {resp.status_code}: {resp.text}"
                )
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"Cannot reach sandbox session server at {base}. "
                "Check if cappycloud-sandbox is running."
            ) from exc

        record = SandboxRecord(
            user_id=user_id,
            chat_id=chat_id,
            sandbox_id=sandbox_id,
            sandbox_name=self._default_name,
            grpc_host=host,
            grpc_port=grpc_port,
            session_root=session_root,
            repos=repos,
            env_slug=legacy_slug,
            worktree_path=legacy_wt,
        )
        await self._store.save(record)
        return record

    @staticmethod
    def _session_payload(
        session_id: str,
        repos: list[dict],
        session_root: str,
        legacy_slug: str,
        legacy_wt_path: str,
        legacy_wt_branch: str,
        branch_name: str,
    ) -> dict:
        return {
            "session_id": session_id,
            "repos": repos,
            "session_root": session_root,
            # Legacy single-repo fields (session_server uses them when repos=[])
            "env_slug": legacy_slug,
            "worktree_path": legacy_wt_path,
            "worktree_branch": legacy_wt_branch or branch_name,
            "base_branch": "",
        }
