"""
CappyCloud Agent Pipeline — Global Environments with Git Worktrees

Key behaviours:
  - Each env_slug maps to ONE persistent environment container (global, not per-user).
  - Each (user_id, chat_id) gets its own git worktree inside the env container.
  - A single openclaude gRPC server per container handles all sessions;
    each ChatRequest carries working_directory → the session's worktree path.
  - GrpcSession is persistent: the gRPC stream stays open between pipe() calls.
  - When openclaude emits ActionRequired, the stream PAUSES and the user sees
    a formatted choice prompt in the chat.
  - The user's next message is detected as a reply and routed back to the stream.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
from collections.abc import Generator
from queue import Empty, Queue
from typing import Optional

from pydantic import BaseModel, Field

from ._environment_manager import EnvironmentManager
from ._grpc_session import GrpcSession, PendingAction, _DONE
from ._session_store import SessionStore

log = logging.getLogger(__name__)


def _agent_database_url() -> str:
    """URL PostgreSQL para o SessionStore (sem prefixo SQLAlchemy ``+asyncpg``)."""
    explicit = os.getenv("PIPELINE_DATABASE_URL", "").strip()
    if explicit:
        return explicit
    fallback = os.getenv("DATABASE_URL", "")
    return fallback.replace("postgresql+asyncpg://", "postgresql://", 1)


def _stable_chat_id(messages: list[dict]) -> str:
    """SHA-1 of the first user message → fallback chat identifier."""
    first = next(
        (m.get("content", "") for m in messages if m.get("role") == "user"),
        "",
    )
    if isinstance(first, list):
        first = " ".join(p.get("text", "") for p in first if isinstance(p, dict))
    return hashlib.sha1(first[:300].encode()).hexdigest()[:16]


def _chat_id_from_body(body: dict, messages: list) -> str:
    """Prefer explicit conversation id from the API (PostgreSQL), else legacy hash."""
    explicit = body.get("conversation_id") or body.get("chat_id")
    if explicit:
        return str(explicit)
    return _stable_chat_id(messages)


def _user_id_from_body(body: dict) -> str:
    """Resolve user id for the (user_id, chat_id) pair."""
    raw = body.get("user")
    if raw is None:
        return str(body.get("user_id") or "anonymous")
    if isinstance(raw, dict):
        return str(raw.get("id") or body.get("user_id") or "anonymous")
    return str(raw)


def _env_slug_from_body(body: dict) -> str:
    """Resolve environment slug from body, defaulting to 'default'."""
    return str(body.get("env_slug") or "default")


def _base_branch_from_body(body: dict) -> str:
    """Resolve base branch for the session worktree (selected by user in UI).

    Empty string signals 'use canonical default from repo_environments',
    which EnvironmentManager resolves internally.
    """
    return str(body.get("base_branch") or "")


def _sse(payload: dict) -> str:
    """Format a dict as a single SSE data line."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _clean_question(question: str) -> str:
    """Remove bracket-formatted choices from question string."""
    return re.sub(r"\s*\[[^\]]+\]", "", question).strip()


class Pipeline:
    class Valves(BaseModel):
        OPENROUTER_API_KEY: str = Field(default="")
        OPENROUTER_MODEL: str = Field(default="anthropic/claude-3.5-sonnet")
        GIT_AUTH_TOKEN: str = Field(default="")
        SANDBOX_IMAGE: str = Field(default="cappycloud-sandbox:latest")
        DOCKER_NETWORK: str = Field(default="cappycloud_net")
        SANDBOX_GRPC_PORT: int = Field(default=50051)
        SANDBOX_IDLE_TIMEOUT: int = Field(default=1800)
        ENV_IDLE_TIMEOUT: int = Field(default=3600)
        REDIS_URL: str = Field(default="redis://redis:6379")
        DATABASE_URL: str = Field(default="")
        CODE_INDEXER_URL: str = Field(default="")

    def __init__(self) -> None:
        self.name = "CappyCloud Agent"
        self.valves = self.Valves(
            OPENROUTER_API_KEY=os.getenv("OPENROUTER_API_KEY", ""),
            OPENROUTER_MODEL=os.getenv(
                "OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet"
            ),
            GIT_AUTH_TOKEN=os.getenv("GIT_AUTH_TOKEN", ""),
            SANDBOX_IMAGE=os.getenv("SANDBOX_IMAGE", "cappycloud-sandbox:latest"),
            DOCKER_NETWORK=os.getenv("DOCKER_NETWORK", "cappycloud_net"),
            SANDBOX_GRPC_PORT=int(os.getenv("SANDBOX_GRPC_PORT", "50051")),
            SANDBOX_IDLE_TIMEOUT=int(os.getenv("SANDBOX_IDLE_TIMEOUT", "1800")),
            ENV_IDLE_TIMEOUT=int(os.getenv("ENV_IDLE_TIMEOUT", "3600")),
            REDIS_URL=os.getenv("REDIS_URL", "redis://redis:6379"),
            DATABASE_URL=_agent_database_url(),
            CODE_INDEXER_URL=os.getenv("CODE_INDEXER_URL", ""),
        )

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._store: Optional[SessionStore] = None
        self._env_manager: Optional[EnvironmentManager] = None
        self._gc_task: Optional[asyncio.Task] = None

        # In-memory map of live gRPC sessions: (user_id, chat_id) → GrpcSession
        self._sessions: dict[tuple[str, str], GrpcSession] = {}

    async def on_startup(self) -> None:
        log.info("CappyCloud agent pipeline starting…")
        self._loop = asyncio.get_running_loop()

        self._store = SessionStore(
            redis_url=self.valves.REDIS_URL,
            database_url=self.valves.DATABASE_URL,
            idle_ttl=self.valves.SANDBOX_IDLE_TIMEOUT,
        )
        await self._store.connect()

        self._env_manager = EnvironmentManager(
            session_store=self._store,
            sandbox_image=self.valves.SANDBOX_IMAGE,
            docker_network=self.valves.DOCKER_NETWORK,
            sandbox_grpc_port=self.valves.SANDBOX_GRPC_PORT,
            openrouter_api_key=self.valves.OPENROUTER_API_KEY,
            openrouter_model=self.valves.OPENROUTER_MODEL,
            git_auth_token=self.valves.GIT_AUTH_TOKEN,
            code_indexer_url=self.valves.CODE_INDEXER_URL,
        )

        self._gc_task = asyncio.create_task(self._gc_loop())
        log.info("CappyCloud agent ready (global env model).")

    async def on_shutdown(self) -> None:
        log.info("CappyCloud agent pipeline shutting down…")
        if self._gc_task:
            self._gc_task.cancel()
        for session in list(self._sessions.values()):
            await session.close()
        self._sessions.clear()
        if self._store:
            await self._store.close()

    def _run(self, coro, timeout: float = 120):
        if self._loop is None:
            raise RuntimeError("Pipeline not started")
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout=timeout)

    def get_env_status(self, env_slug: str) -> dict:
        """Return the current environment status for a slug."""
        if self._env_manager is None:
            return {"status": "none", "container_id": None}
        return self._run(self._env_manager.get_env_status(env_slug), timeout=30)

    def wake_env(self, env_slug: str) -> None:
        """Trigger environment creation or restart (fire-and-forget).

        repo_url and branch are resolved internally by EnvironmentManager.
        """
        if self._loop is None or self._env_manager is None:
            return
        asyncio.run_coroutine_threadsafe(
            self._env_manager._get_or_create_env(env_slug),
            self._loop,
        )

    def destroy_env(self, env_slug: str) -> None:
        """Stop and remove environment container for a slug (fire-and-forget)."""
        if self._loop is None or self._env_manager is None:
            return
        asyncio.run_coroutine_threadsafe(
            self._env_manager.destroy_env(env_slug),
            self._loop,
        )

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: list,
        body: dict,
    ) -> Generator[str, None, None]:
        user_id = _user_id_from_body(body)
        chat_id = _chat_id_from_body(body, messages)
        env_slug = _env_slug_from_body(body)
        base_branch = _base_branch_from_body(body)
        session_key = (user_id, chat_id)

        log.info(
            "pipe() user=%s chat=%s env=%s msg=%r",
            user_id,
            chat_id,
            env_slug,
            user_message[:80],
        )

        session: Optional[GrpcSession] = self._sessions.get(session_key)

        if session and session.is_alive() and session.pending_action:
            log.info("Routing reply to pending action: %r", user_message)
            self._run(session.send_input(user_message), timeout=10)

        elif session and session.is_alive():
            log.info("Continuing live session in worktree")
            self._run(session.send_message(user_message), timeout=10)

        else:
            if session:
                self._run(session.close(), timeout=5)
                del self._sessions[session_key]

            try:
                sandbox = self._run(
                    self._env_manager.get_or_create_session(
                        user_id=user_id,
                        chat_id=chat_id,
                        env_slug=env_slug,
                        base_branch=base_branch,
                    ),
                    timeout=180,
                )
            except TimeoutError as exc:
                yield _sse({"type": "error", "message": f"Timeout ao iniciar o agente. {exc}"})
                return
            except Exception as exc:
                log.exception("Falha ao criar sessão")
                yield _sse({"type": "error", "message": f"Erro ao iniciar o agente: {exc}"})
                return

            working_directory = sandbox.worktree_path or f"/repos/{env_slug}"

            session = GrpcSession(
                container_ip=sandbox.container_ip,
                grpc_port=sandbox.grpc_port,
                session_id=f"{user_id}:{chat_id}",
                model=self.valves.OPENROUTER_MODEL,
                working_directory=working_directory,
            )
            try:
                self._run(session.start(user_message), timeout=30)
            except Exception as exc:
                log.exception("Falha ao iniciar sessão gRPC")
                yield _sse({"type": "error", "message": f"Erro ao conectar ao agente: {exc}"})
                return

            self._sessions[session_key] = session

        out_q: Queue = Queue()

        asyncio.run_coroutine_threadsafe(
            session.drain_to(out_q), self._loop
        )

        did_yield = False
        while True:
            try:
                event_type, data = out_q.get(timeout=300)
            except Empty:
                yield _sse({"type": "error", "message": "Timeout: agente sem resposta por 5 minutos."})
                break

            if event_type is _DONE:
                if isinstance(data, str):
                    yield _sse({"type": "error", "message": f"Erro do agente: {data}"})
                    did_yield = True
                elif not did_yield:
                    yield _sse({
                        "type": "error",
                        "message": (
                            "O agente não devolveu texto. "
                            "Confirma OPENROUTER_API_KEY, o modelo e se o sandbox está a correr."
                        ),
                    })
                    did_yield = True
                if session_key in self._sessions:
                    del self._sessions[session_key]
                break

            elif event_type == "text":
                did_yield = True
                yield _sse({"type": "text", "content": data})

            elif event_type == "tool_start":
                yield _sse({"type": "tool_start", **data})

            elif event_type == "tool_result":
                yield _sse({"type": "tool_result", **data})

            elif event_type == "action":
                action: PendingAction = data
                log.info(
                    "[%s] Auto-approving action: %s",
                    session_key,
                    action.question[:80],
                )
                self._run(session.send_input("yes"), timeout=10)
                asyncio.run_coroutine_threadsafe(
                    session.drain_to(out_q), self._loop
                )

            elif event_type == "timeout":
                yield _sse({"type": "error", "message": "Timeout: agente demorou muito para responder."})
                break

    async def _gc_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(300)
                dead = [k for k, s in self._sessions.items() if not s.is_alive()]
                for k in dead:
                    await self._sessions.pop(k).close()
                if self._env_manager:
                    await self._env_manager.gc_expired()
                    await self._env_manager.gc_idle_envs(self.valves.ENV_IDLE_TIMEOUT)
            except asyncio.CancelledError:
                break
            except Exception:
                log.exception("GC loop error")

