"""
CappyCloud Agent Pipeline — DB-backed, UI-independent agent lifecycle.

Key behaviours:
  - Each env_slug maps to ONE persistent environment container.
  - Each (user_id, chat_id) gets its own git worktree inside the env container.
  - Agent execution is managed by TaskDispatcher + TaskRunner, fully decoupled from HTTP.
  - pipe() dispatches a task and streams agent_events from the DB with SSE cursor.
"""

from __future__ import annotations

import asyncio
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


def _db_url() -> str:
    explicit = os.getenv("PIPELINE_DATABASE_URL", "").strip()
    if explicit:
        return explicit
    return os.getenv("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://", 1)


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
            DATABASE_URL=_db_url(),
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
        log.info("CappyCloud agent ready.")

    async def on_shutdown(self) -> None:
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

    def get_env_status(self, env_slug: str) -> dict:
        if self._env_manager is None:
            return {"status": "none", "container_id": None}
        return self._run(self._env_manager.get_env_status(env_slug), timeout=30)

    def wake_env(self, env_slug: str) -> None:
        if self._loop and self._env_manager:
            asyncio.run_coroutine_threadsafe(
                self._env_manager._get_or_create_env(env_slug), self._loop
            )

    def destroy_env(self, env_slug: str) -> None:
        if self._loop and self._env_manager:
            asyncio.run_coroutine_threadsafe(
                self._env_manager.destroy_env(env_slug), self._loop
            )

    def cancel_conversation(self, conversation_id: str) -> bool:
        if self._dispatcher is None:
            return False
        return self._run(self._dispatcher.cancel_for_conversation(conversation_id), timeout=15)

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: list,
        body: dict,
    ) -> Generator[str, None, None]:
        if self._dispatcher is None:
            yield _sse({"type": "error", "message": "Pipeline não inicializado."})
            return

        conversation_id = str(body.get("conversation_id") or "")
        env_slug = str(body.get("env_slug") or "default")
        base_branch = str(body.get("base_branch") or "")
        cursor = body.get("cursor")
        try:
            cursor = int(cursor) if cursor is not None else None
        except (TypeError, ValueError):
            cursor = None

        task_id: Optional[str] = self._run(
            self._dispatcher.get_active_task_id(conversation_id or "__none__"), timeout=10
        )
        runner = self._dispatcher.get_runner(task_id) if task_id else None

        if runner and runner.is_alive() and runner.pending_action:
            self._run(self._dispatcher.send_input(task_id, user_message), timeout=10)
        elif runner and runner.is_alive():
            self._run(self._dispatcher.send_message(task_id, user_message), timeout=10)
        else:
            task_id = self._run(
                self._dispatcher.dispatch(
                    prompt=user_message,
                    env_slug=env_slug,
                    conversation_id=conversation_id or None,
                    triggered_by="user",
                    base_branch=base_branch,
                ),
                timeout=10,
            )

        yield from self._stream_events(task_id, cursor)

    def _stream_events(self, task_id: str, cursor: Optional[int]) -> Generator[str, None, None]:
        import queue as _queue

        import asyncpg as _asyncpg

        db_url = self.valves.DATABASE_URL
        out_q: _queue.Queue = _queue.Queue()

        async def _produce() -> None:
            pool = await _asyncpg.create_pool(db_url, min_size=1, max_size=2)
            try:
                last_id = cursor
                while True:
                    if last_id is None:
                        rows = await pool.fetch(
                            "SELECT id, event_type, data FROM agent_events "
                            "WHERE task_id=$1::uuid ORDER BY id LIMIT 50",
                            task_id,
                        )
                    else:
                        rows = await pool.fetch(
                            "SELECT id, event_type, data FROM agent_events "
                            "WHERE task_id=$1::uuid AND id>$2 ORDER BY id LIMIT 50",
                            task_id, last_id,
                        )
                    for row in rows:
                        last_id = row["id"]
                        data = row["data"]
                        if isinstance(data, str):
                            data = json.loads(data)
                        out_q.put((row["event_type"], data, last_id))
                    status_row = await pool.fetchrow(
                        "SELECT status FROM agent_tasks WHERE id=$1::uuid", task_id
                    )
                    if (status_row and status_row["status"] in ("done", "error")) and not rows:
                        break
                    if not rows:
                        await asyncio.sleep(0.5)
            finally:
                out_q.put(None)
                await pool.close()

        asyncio.run_coroutine_threadsafe(_produce(), self._loop)

        while True:
            item = out_q.get(timeout=310)
            if item is None:
                break
            event_type, data, eid = item
            yield _sse({"type": event_type, "cursor": eid, **(data if data else {})})

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
