"""TaskDispatcher — orquestra o ciclo de vida das AgentTasks."""

from __future__ import annotations

import asyncio
import logging
import uuid

import asyncpg

from ._environment_manager import EnvironmentManager
from ._orphan_recovery import reconnect_orphaned_tasks
from ._session_store import SessionStore
from ._task_events import (
    insert_error_event,
    insert_task,
    update_task_status,
)
from ._task_launcher import launch_runner
from ._task_runner import TaskRunner

log = logging.getLogger(__name__)


class TaskDispatcher:
    """Gestiona o mapa de TaskRunners activos e o dispatch de novas tasks."""

    def __init__(
        self,
        env_manager: EnvironmentManager,
        session_store: SessionStore,
        db_url: str,
        openrouter_model: str,
    ) -> None:
        self._env_manager = env_manager
        self._store = session_store
        self._db_url = db_url
        self._model = openrouter_model
        self._pool: asyncpg.Pool | None = None
        self._runners: dict[str, TaskRunner] = {}
        self._launch_tasks: set[asyncio.Task] = set()

    async def start(self) -> None:
        """Conecta ao DB e reconecta tasks órfãs de um restart anterior."""
        self._pool = await asyncpg.create_pool(self._db_url, min_size=1, max_size=5)
        await self._reconnect_orphaned_tasks()

    async def stop(self) -> None:
        for task in list(self._launch_tasks):
            task.cancel()
        if self._launch_tasks:
            await asyncio.gather(*self._launch_tasks, return_exceptions=True)
        self._launch_tasks.clear()
        for runner in list(self._runners.values()):
            await runner.close()
        self._runners.clear()
        if self._pool:
            await self._pool.close()

    async def dispatch(
        self,
        prompt: str,
        conversation_id: str | None = None,
        triggered_by: str = "user",
        trigger_payload: dict | None = None,
        repos: list | None = None,
        session_root: str = "",
        sandbox_id: str = "",
        override_model: str | None = None,
        sandbox_session_url: str = "",
        attachments: list[dict] | None = None,
    ) -> str:
        """Cria uma agent_task e arranca o runner; retorna o task_id (UUID).

        ``attachments``: lista de dicts ``{mime_type, data, original_filename}``
        que viajam até ao gRPC (multimodal nativo). Caller deve garantir que o
        modelo escolhido suporta ``vision`` antes de passar bytes binários —
        modelos text-only respondem 4xx.
        """
        task_id = str(uuid.uuid4())
        await insert_task(
            self._pool,
            task_id,
            conversation_id,
            prompt,
            triggered_by,
            trigger_payload or {},
        )
        launch_task = asyncio.create_task(
            self._launch_runner(
                task_id,
                prompt,
                conversation_id,
                repos=repos or [],
                session_root=session_root,
                sandbox_id=sandbox_id,
                override_model=override_model,
                sandbox_session_url=sandbox_session_url,
                attachments=attachments,
            ),
            name=f"dispatch-{task_id[:8]}",
        )
        self._launch_tasks.add(launch_task)
        launch_task.add_done_callback(self._launch_tasks.discard)
        return task_id

    def get_runner(self, task_id: str) -> TaskRunner | None:
        return self._runners.get(task_id)

    def get_runner_for_conversation(self, conversation_id: str) -> TaskRunner | None:
        """Retorna o runner activo da conversa (status running ou paused)."""
        for _task_id, runner in self._runners.items():
            if runner.is_alive():
                return runner
        return None

    async def get_active_task_id(self, conversation_id: str) -> str | None:
        """Retorna o task_id da task running/paused para uma conversa."""
        if not self._pool:
            return None
        row = await self._pool.fetchrow(
            """
            SELECT id FROM agent_tasks
            WHERE conversation_id = $1::uuid
              AND status IN ('pending','running','paused')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            conversation_id,
        )
        return str(row["id"]) if row else None

    async def send_input(self, task_id: str, reply: str) -> bool:
        """Encaminha resposta do utilizador para a task pausada."""
        runner = self._runners.get(task_id)
        if runner and runner.is_alive() and runner.pending_action:
            await runner.send_input(reply)
            return True
        return False

    async def send_message(
        self,
        task_id: str,
        message: str,
        attachments: list[dict] | None = None,
    ) -> bool:
        """Envia nova mensagem numa task running (nova turn)."""
        runner = self._runners.get(task_id)
        if runner and runner.is_alive() and not runner.pending_action:
            await runner.send_message(message, attachments=attachments)
            return True
        return False

    async def cancel_task(self, task_id: str) -> bool:
        """Cancela uma task em execução."""
        runner = self._runners.pop(task_id, None)
        if runner:
            await runner.close()
        await update_task_status(self._pool, task_id, "error")
        await insert_error_event(
            self._pool, task_id, "Tarefa cancelada pelo utilizador."
        )
        return True

    async def cancel_for_conversation(self, conversation_id: str) -> bool:
        """Cancela a task activa da conversa, se houver."""
        task_id = await self.get_active_task_id(conversation_id)
        if not task_id:
            return False
        return await self.cancel_task(task_id)

    async def gc(self) -> None:
        """Remove runners mortos do mapa em memória."""
        dead = [tid for tid, r in self._runners.items() if not r.is_alive()]
        for tid in dead:
            runner = self._runners.pop(tid)
            await runner.close()
        log.debug(
            "GC: removed %d dead runners (%d active)", len(dead), len(self._runners)
        )

    async def _launch_runner(
        self,
        task_id: str,
        prompt: str,
        conversation_id: str | None,
        repos: list | None = None,
        session_root: str = "",
        sandbox_id: str = "",
        override_model: str | None = None,
        sandbox_session_url: str = "",
        attachments: list[dict] | None = None,
    ) -> None:
        """Cria a sessão, inicia a GrpcSession e arranca o TaskRunner."""
        await launch_runner(
            self,
            task_id,
            prompt,
            conversation_id,
            repos=repos,
            session_root=session_root,
            sandbox_id=sandbox_id,
            override_model=override_model,
            sandbox_session_url=sandbox_session_url,
            attachments=attachments,
        )

    async def _reconnect_orphaned_tasks(self) -> None:
        await reconnect_orphaned_tasks(self._pool)
