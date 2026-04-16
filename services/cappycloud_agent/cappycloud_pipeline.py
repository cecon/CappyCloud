"""
CappyCloud Agent Pipeline — DB-backed, UI-independent agent lifecycle.

Key behaviours:
  - Each env_slug maps to ONE persistent environment container (global, not per-user).
  - Each (user_id, chat_id) gets its own git worktree inside the env container.
  - Agent execution is managed by TaskDispatcher + TaskRunner, fully decoupled from HTTP.
  - pipe() no longer drives the gRPC stream; it dispatches a task and streams
    agent_events from the DB — so the UI can disconnect/reconnect freely.
  - SSE uses a cursor (last agent_event.id) for resumption.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from collections.abc import Generator
from typing import Optional

from pydantic import BaseModel, Field

from ._environment_manager import EnvironmentManager
from ._session_store import SessionStore
from ._task_dispatcher import TaskDispatcher

log = logging.getLogger(__name__)


def _agent_database_url() -> str:
    """URL PostgreSQL para o TaskDispatcher (sem prefixo SQLAlchemy ``+asyncpg``)."""
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
    explicit = body.get("conversation_id") or body.get("chat_id")
    if explicit:
        return str(explicit)
    return _stable_chat_id(messages)


def _user_id_from_body(body: dict) -> str:
    raw = body.get("user")
    if raw is None:
        return str(body.get("user_id") or "anonymous")
    if isinstance(raw, dict):
        return str(raw.get("id") or body.get("user_id") or "anonymous")
    return str(raw)


def _env_slug_from_body(body: dict) -> str:
    return str(body.get("env_slug") or "default")


def _base_branch_from_body(body: dict) -> str:
    return str(body.get("base_branch") or "")


def _cursor_from_body(body: dict) -> Optional[int]:
    """Cursor SSE: último agent_event.id já visto pelo cliente."""
    raw = body.get("cursor") or body.get("last_event_id")
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


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
            OPENROUTER_MODEL=os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet"),
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
        self._dispatcher: Optional[TaskDispatcher] = None
        self._gc_task: Optional[asyncio.Task] = None

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

        self._dispatcher = TaskDispatcher(
            env_manager=self._env_manager,
            session_store=self._store,
            db_url=self.valves.DATABASE_URL,
            openrouter_model=self.valves.OPENROUTER_MODEL,
        )
        await self._dispatcher.start()

        self._gc_task = asyncio.create_task(self._gc_loop())
        log.info("CappyCloud agent ready (DB-backed lifecycle).")

    async def on_shutdown(self) -> None:
        log.info("CappyCloud agent pipeline shutting down…")
        if self._gc_task:
            self._gc_task.cancel()
        if self._dispatcher:
            await self._dispatcher.stop()
        if self._store:
            await self._store.close()

    def _run(self, coro, timeout: float = 120):
        if self._loop is None:
            raise RuntimeError("Pipeline not started")
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout=timeout)

    # ── Environment management (unchanged public API) ─────────────

    def get_env_status(self, env_slug: str) -> dict:
        if self._env_manager is None:
            return {"status": "none", "container_id": None}
        return self._run(self._env_manager.get_env_status(env_slug), timeout=30)

    def wake_env(self, env_slug: str) -> None:
        if self._loop is None or self._env_manager is None:
            return
        asyncio.run_coroutine_threadsafe(
            self._env_manager._get_or_create_env(env_slug),
            self._loop,
        )

    def destroy_env(self, env_slug: str) -> None:
        if self._loop is None or self._env_manager is None:
            return
        asyncio.run_coroutine_threadsafe(
            self._env_manager.destroy_env(env_slug),
            self._loop,
        )

    # ── pipe() — thin SSE layer over DB events ────────────────────

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: list,
        body: dict,
    ) -> Generator[str, None, None]:
        """Entry point for each user message.

        1. Resolves task context (existing active task or dispatches a new one).
        2. Streams agent_events from DB as SSE, starting from cursor.
        """
        if self._dispatcher is None:
            yield _sse({"type": "error", "message": "Pipeline não inicializado."})
            return

        conversation_id = _chat_id_from_body(body, messages)
        env_slug = _env_slug_from_body(body)
        base_branch = _base_branch_from_body(body)
        cursor = _cursor_from_body(body)

        # Check if there is an active task with a pending action
        task_id: Optional[str] = self._run(
            self._dispatcher.get_active_task_id(conversation_id), timeout=10
        )

        runner = self._dispatcher.get_runner(task_id) if task_id else None

        if runner and runner.is_alive() and runner.pending_action:
            # Route user reply to the paused stream
            self._run(self._dispatcher.send_input(task_id, user_message), timeout=10)

        elif runner and runner.is_alive():
            # Continue existing session with new turn
            self._run(self._dispatcher.send_message(task_id, user_message), timeout=10)

        else:
            # Dispatch a new task — returns immediately, runner executes in background
            task_id = self._run(
                self._dispatcher.dispatch(
                    prompt=user_message,
                    env_slug=env_slug,
                    conversation_id=conversation_id,
                    triggered_by="user",
                    base_branch=base_branch,
                ),
                timeout=10,
            )

        # Stream agent_events from DB as SSE
        yield from self._stream_events(task_id, cursor)

    def _stream_events(
        self, task_id: str, cursor: Optional[int]
    ) -> Generator[str, None, None]:
        """Poll agent_events from DB and yield as SSE until task is terminal."""
        import asyncpg as _asyncpg  # local import to avoid circular issues

        db_url = self.valves.DATABASE_URL

        async def _fetch_events(pool, after_id: Optional[int], limit: int = 50):
            if after_id is None:
                return await pool.fetch(
                    "SELECT id, event_type, data FROM agent_events WHERE task_id=$1::uuid ORDER BY id LIMIT $2",
                    task_id,
                    limit,
                )
            return await pool.fetch(
                "SELECT id, event_type, data FROM agent_events WHERE task_id=$1::uuid AND id>$2 ORDER BY id LIMIT $3",
                task_id,
                after_id,
                limit,
            )

        async def _task_status(pool) -> str:
            row = await pool.fetchrow(
                "SELECT status FROM agent_tasks WHERE id=$1::uuid", task_id
            )
            return row["status"] if row else "error"

        async def _run_stream():
            pool = await _asyncpg.create_pool(db_url, min_size=1, max_size=2)
            try:
                last_id = cursor
                while True:
                    rows = await _fetch_events(pool, last_id)
                    for row in rows:
                        last_id = row["id"]
                        data = row["data"]
                        if isinstance(data, str):
                            data = json.loads(data)
                        yield row["event_type"], data, last_id

                    status = await _task_status(pool)
                    if status in ("done", "error"):
                        return

                    if not rows:
                        await asyncio.sleep(0.5)
            finally:
                await pool.close()

        import queue as _queue

        out_q: _queue.Queue = _queue.Queue()

        async def _produce():
            try:
                async for event_type, data, eid in _run_stream():
                    out_q.put((event_type, data, eid))
                out_q.put(None)  # sentinel
            except Exception as exc:
                out_q.put(("__error__", {"message": str(exc)}, -1))
                out_q.put(None)

        asyncio.run_coroutine_threadsafe(_produce(), self._loop)

        while True:
            item = out_q.get(timeout=310)
            if item is None:
                break
            event_type, data, eid = item
            if event_type == "__error__":
                yield _sse({"type": "error", **data})
                break
            yield _sse({"type": event_type, "cursor": eid, **({} if not data else data)})

    # ── GC loop ───────────────────────────────────────────────────

    async def _gc_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(300)
                if self._dispatcher:
                    await self._dispatcher.gc()
                if self._env_manager:
                    await self._env_manager.gc_expired()
                    await self._env_manager.gc_idle_envs(self.valves.ENV_IDLE_TIMEOUT)
            except asyncio.CancelledError:
                break
            except Exception:
                log.exception("GC loop error")
