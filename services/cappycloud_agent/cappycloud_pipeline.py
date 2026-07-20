"""
CappyCloud Agent Pipeline — DB-backed, UI-independent agent lifecycle.

Key behaviours:
  - One fixed environment container (cappycloud-sandbox) always running.
  - Each (user_id, chat_id) gets its own git worktree inside the sandbox.
  - Agent execution is managed by TaskDispatcher + TaskRunner, fully decoupled from HTTP.
  - pipe() dispatches a task and streams agent_events from the DB with SSE cursor.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Generator

from pydantic import BaseModel, Field

from ._agent_context import (
    build_prompt_with_agent,
    load_agent_context,
    load_repo_agent_profiles,
)
from ._environment_manager import EnvironmentManager
from ._pipeline_event_stream import stream_task_events
from ._pipeline_helpers import (
    db_url,
    inject_repo_context,
    push_mcp_config,
    resolve_text_model_id,
    sse,
)
from ._session_store import SessionStore
from ._signoz_context import (
    build_signoz_context_section,
    fetch_signoz_service_names,
    has_enabled_signoz_mcp,
)
from ._task_dispatcher import TaskDispatcher
from ._grpc_helpers import sanitize_permission_mode

log = logging.getLogger(__name__)


class Pipeline:
    class Valves(BaseModel):
        OPENROUTER_API_KEY: str = Field(default="")
        OPENROUTER_MODEL: str = Field(default="anthropic/claude-3.5-sonnet")
        SANDBOX_HOST: str = Field(default="cappycloud-sandbox")
        SANDBOX_GRPC_PORT: int = Field(default=50051)
        SANDBOX_SESSION_PORT: int = Field(default=8080)
        SANDBOX_IDLE_TIMEOUT: int = Field(default=1800)
        REDIS_URL: str = Field(default="redis://redis:6379")
        DATABASE_URL: str = Field(default="")

    def __init__(self) -> None:
        self.name = "CappyCloud Agent"
        self.valves = self.Valves(
            OPENROUTER_API_KEY=os.getenv("OPENROUTER_API_KEY", ""),
            OPENROUTER_MODEL=os.getenv(
                "OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet"
            ),
            SANDBOX_HOST=os.getenv("SANDBOX_HOST", "cappycloud-sandbox"),
            SANDBOX_GRPC_PORT=int(os.getenv("SANDBOX_GRPC_PORT", "50051")),
            SANDBOX_SESSION_PORT=int(os.getenv("SANDBOX_SESSION_PORT", "8080")),
            SANDBOX_IDLE_TIMEOUT=int(os.getenv("SANDBOX_IDLE_TIMEOUT", "1800")),
            REDIS_URL=os.getenv("REDIS_URL", "redis://redis:6379"),
            DATABASE_URL=db_url(),
        )
        self._loop: asyncio.AbstractEventLoop | None = None
        self._store: SessionStore | None = None
        self._env_manager: EnvironmentManager | None = None
        self._dispatcher: TaskDispatcher | None = None
        self._gc_task: asyncio.Task | None = None

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
            sandbox_host=self.valves.SANDBOX_HOST,
            sandbox_grpc_port=self.valves.SANDBOX_GRPC_PORT,
            sandbox_session_port=self.valves.SANDBOX_SESSION_PORT,
            database_url=self.valves.DATABASE_URL,
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
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(
            timeout=timeout
        )

    def cancel_conversation(self, conversation_id: str) -> bool:
        if self._dispatcher is None:
            return False
        return bool(
            self._run(
                self._dispatcher.cancel_for_conversation(conversation_id), timeout=15
            )
        )

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: list,
        body: dict,
    ) -> Generator[str]:
        if self._dispatcher is None:
            yield sse({"type": "error", "message": "Pipeline não inicializado."})
            return

        yield sse(
            {
                "type": "status",
                "message": "Preparando contexto da conversa.",
            }
        )

        conversation_id = str(body.get("conversation_id") or "")
        user_id = str(body.get("user_id") or "")
        repos = body.get("repos") or []
        session_root = str(body.get("session_root") or "")
        sandbox_id = str(body.get("sandbox_id") or "")
        permission_mode = sanitize_permission_mode(body.get("permission_mode"))
        cursor = body.get("cursor")
        try:
            cursor = int(cursor) if cursor is not None else None
        except (TypeError, ValueError):
            cursor = None

        action_reply = bool(body.get("action_reply"))
        if action_reply:
            task_id = self._run(
                self._dispatcher.get_active_task_id(conversation_id or "__none__"),
                timeout=10,
            )
            runner = self._dispatcher.get_runner(task_id) if task_id else None
            if task_id and runner and runner.is_alive() and runner.pending_action:
                self._run(self._dispatcher.send_input(task_id, user_message), timeout=10)
                yield from self._stream_events(task_id, cursor)
                return
            if task_id:
                yield from self._stream_events(
                    task_id,
                    cursor,
                    stop_when_caught_up=True,
                )
                return
            yield sse({"type": "done", "model_used": None})
            return

        repo_ids: list[str] = [r["repo_id"] for r in repos if r.get("repo_id")]

        skills_top: list[dict] = []
        agent_profiles: list[dict] = []
        if repo_ids:
            try:
                skills_top = self._run(
                    load_agent_context(
                        self.valves.DATABASE_URL,
                        user_message,
                        repo_ids=repo_ids or None,
                    ),
                    timeout=10,
                )
            except Exception as exc:
                log.warning("Falha ao carregar agent_context: %s", exc)
        if repos:
            try:
                agent_profiles = self._run(
                    load_repo_agent_profiles(
                        self.valves.DATABASE_URL,
                        repos,
                        sandbox_id=sandbox_id,
                    ),
                    timeout=5,
                )
            except Exception as exc:
                log.warning("Falha ao carregar repo_agent_profiles: %s", exc)

        sandbox_host = self.valves.SANDBOX_HOST
        sandbox_session_port = self.valves.SANDBOX_SESSION_PORT
        if self._env_manager is not None:
            try:
                sandbox_host, _, sandbox_session_port, _ = self._run(
                    self._env_manager._resolve_sandbox_endpoint(sandbox_id),
                    timeout=5,
                )
            except Exception as exc:
                log.warning("Falha ao resolver endpoint da sandbox %s: %s", sandbox_id, exc)
        sandbox_session_url = f"http://{sandbox_host}:{sandbox_session_port}"

        # NOTA: a estrutura top-level do worktree é injetada pelo dispatcher,
        # depois de o worktree ser efetivamente criado pelo EnvironmentManager.
        # Tentar obtê-la aqui falha sempre na primeira mensagem (worktree ainda
        # não existe → /worktree/ls-files devolve 500).
        prompt = build_prompt_with_agent(
            user_message,
            skills_top,
            sandbox_session_url,
            repos=repos,
            session_root=session_root,
            worktree_top_level=None,
            agent_profiles=agent_profiles,
        )
        prompt = inject_repo_context(prompt, repos, session_root)

        # Injeta contexto SigNoz (service.name por repo) se houver configuração.
        repo_ids_for_signoz = [r["repo_id"] for r in repos if r.get("repo_id")]
        if repo_ids_for_signoz:
            try:
                signoz_names = self._run(
                    fetch_signoz_service_names(db_url(), repo_ids_for_signoz),
                    timeout=5,
                )
                signoz_mcp_available = self._run(
                    has_enabled_signoz_mcp(db_url(), sandbox_id),
                    timeout=5,
                )
                signoz_section = build_signoz_context_section(
                    repos,
                    signoz_names,
                    mcp_available=signoz_mcp_available,
                )
                if signoz_section:
                    from ._agent_context import inject_section_before_user_message

                    prompt = inject_section_before_user_message(prompt, signoz_section)
            except Exception as exc:
                log.warning("[Signoz] falha ao injetar contexto: %s", exc)

        task_id: str | None = self._run(
            self._dispatcher.get_active_task_id(conversation_id or "__none__"),
            timeout=10,
        )
        runner = self._dispatcher.get_runner(task_id) if task_id else None

        # ``attachments_payload`` chega da API como lista de dicts já com bytes.
        # Carregar bytes de imagens em memória aqui é aceitável: o pipeline já
        # tem o upper-bound do upload (8MB cada) validado no endpoint HTTP.
        attachments_payload = body.get("attachments_payload") or None

        try:
            override_model = self._run(
                resolve_text_model_id(db_url(), body.get("override_model")),
                timeout=5,
            )
        except Exception as exc:
            log.warning("[Models] resolução do modelo free falhou: %s", exc)
            override_model = None

        dispatch_kwargs = {
            "repos": repos,
            "user_id": user_id,
            "session_root": session_root,
            "sandbox_id": sandbox_id,
            "override_model": override_model,
            "permission_mode": permission_mode,
            "sandbox_session_url": sandbox_session_url,
            "attachments": attachments_payload,
        }

        # Envia config MCP ao sandbox antes de cada dispatch (idempotente).
        yield sse(
            {
                "type": "status",
                "message": "Sincronizando configuração do agente.",
            }
        )
        self._run(
            push_mcp_config(db_url(), sandbox_id, sandbox_session_url),
            timeout=8,
        )

        if task_id and runner and runner.is_alive() and runner.pending_action:
            self._run(self._dispatcher.send_input(task_id, user_message), timeout=10)
        elif runner and runner.is_alive():
            log.info(
                "pipe(): runner %s mid-stream — cancelling and re-dispatching for %s",
                task_id[:8] if task_id else "?",
                conversation_id[:8] if conversation_id else "?",
            )
            self._run(
                self._dispatcher.cancel_for_conversation(conversation_id), timeout=10
            )
            task_id = self._run(
                self._dispatcher.dispatch(
                    prompt=prompt,
                    conversation_id=conversation_id or None,
                    triggered_by="user",
                    **dispatch_kwargs,
                ),
                timeout=10,
            )
        else:
            task_id = self._run(
                self._dispatcher.dispatch(
                    prompt=prompt,
                    conversation_id=conversation_id or None,
                    triggered_by="user",
                    **dispatch_kwargs,
                ),
                timeout=10,
            )

        if task_id is None:
            yield sse(
                {
                    "type": "error",
                    "message": "Não foi possível iniciar a tarefa do agente.",
                }
            )
            return

        yield from self._stream_events(task_id, cursor)

    def _stream_events(
        self,
        task_id: str,
        cursor: int | None,
        *,
        stop_when_caught_up: bool = False,
    ) -> Generator[str]:
        if self._loop is None:
            return
        yield from stream_task_events(
            loop=self._loop,
            database_url=self.valves.DATABASE_URL,
            task_id=task_id,
            cursor=cursor,
            stop_when_caught_up=stop_when_caught_up,
        )

    async def _gc_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(300)
                if self._dispatcher:
                    await self._dispatcher.gc()
                if self._env_manager:
                    await self._env_manager.gc_expired()
            except asyncio.CancelledError:
                break
            except Exception:
                log.exception("GC loop error")
