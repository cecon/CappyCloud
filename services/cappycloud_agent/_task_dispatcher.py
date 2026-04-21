"""TaskDispatcher — orquestra o ciclo de vida das AgentTasks."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

import asyncpg

from ._environment_manager import EnvironmentManager
from ._grpc_session import GrpcSession
from ._session_store import SessionStore
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

        # task_id (str) → TaskRunner
        self._runners: dict[str, TaskRunner] = {}

    # ── Lifecycle ─────────────────────────────────────────────────

    async def start(self) -> None:
        """Conecta ao DB e reconecta tasks órfãs de um restart anterior."""
        self._pool = await asyncpg.create_pool(self._db_url, min_size=1, max_size=5)
        await self._reconnect_orphaned_tasks()

    async def stop(self) -> None:
        for runner in list(self._runners.values()):
            await runner.close()
        self._runners.clear()
        if self._pool:
            await self._pool.close()

    # ── Dispatch ──────────────────────────────────────────────────

    async def dispatch(
        self,
        prompt: str,
        conversation_id: str | None = None,
        triggered_by: str = "user",
        trigger_payload: dict | None = None,
        repos: list | None = None,
        session_root: str = "",
        sandbox_id: str = "",
    ) -> str:
        """Cria um agent_task no DB e arranca o TaskRunner correspondente.

        Retorna o task_id (UUID str) para que o caller possa fazer SSE.
        """
        task_id = str(uuid.uuid4())
        await self._insert_task(
            task_id=task_id,
            conversation_id=conversation_id,
            prompt=prompt,
            triggered_by=triggered_by,
            trigger_payload=trigger_payload or {},
        )
        asyncio.create_task(
            self._launch_runner(
                task_id, prompt, conversation_id,
                repos=repos or [], session_root=session_root, sandbox_id=sandbox_id,
            ),
            name=f"dispatch-{task_id[:8]}",
        )
        return task_id

    # ── Access to active runners ──────────────────────────────────

    def get_runner(self, task_id: str) -> TaskRunner | None:
        return self._runners.get(task_id)

    def get_runner_for_conversation(self, conversation_id: str) -> TaskRunner | None:
        """Retorna o runner activo da conversa (status running ou paused)."""
        for task_id, runner in self._runners.items():
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

    # ── Input routing ─────────────────────────────────────────────

    async def send_input(self, task_id: str, reply: str) -> bool:
        """Encaminha resposta do utilizador para a task pausada. Retorna True se OK."""
        runner = self._runners.get(task_id)
        if runner and runner.is_alive() and runner.pending_action:
            await runner.send_input(reply)
            return True
        return False

    async def send_message(self, task_id: str, message: str) -> bool:
        """Envia nova mensagem numa task running (nova turn). Retorna True se OK."""
        runner = self._runners.get(task_id)
        if runner and runner.is_alive() and not runner.pending_action:
            await runner.send_message(message)
            return True
        return False

    async def cancel_task(self, task_id: str) -> bool:
        """Cancela uma task em execução. Retorna True se havia algo a cancelar."""
        runner = self._runners.pop(task_id, None)
        if runner:
            await runner.close()
        await self._update_task_status(task_id, "error")
        await self._insert_error_event(task_id, "Tarefa cancelada pelo utilizador.")
        return True

    async def cancel_for_conversation(self, conversation_id: str) -> bool:
        """Cancela a task activa da conversa. Retorna True se havia algo a cancelar."""
        task_id = await self.get_active_task_id(conversation_id)
        if not task_id:
            return False
        return await self.cancel_task(task_id)

    # ── GC ────────────────────────────────────────────────────────

    async def gc(self) -> None:
        """Remove runners mortos do mapa em memória."""
        dead = [tid for tid, r in self._runners.items() if not r.is_alive()]
        for tid in dead:
            runner = self._runners.pop(tid)
            await runner.close()
        log.debug("GC: removed %d dead runners (%d active)", len(dead), len(self._runners))

    # ── Internal ──────────────────────────────────────────────────

    async def _launch_runner(
        self,
        task_id: str,
        prompt: str,
        conversation_id: str | None,
        repos: list | None = None,
        session_root: str = "",
        sandbox_id: str = "",
    ) -> None:
        """Cria a sessão, inicia a GrpcSession e arranca o TaskRunner."""
        user_id = conversation_id or "system"
        chat_id = task_id

        try:
            sandbox = await self._env_manager.get_or_create_session(
                user_id=user_id,
                chat_id=chat_id,
                repos=repos or [],
                sandbox_id=sandbox_id,
            )
        except Exception as exc:
            log.exception("[Dispatcher] Falha ao criar sessão para task %s", task_id[:8])
            await self._update_task_status(task_id, "error")
            await self._insert_error_event(task_id, str(exc))
            return

        working_directory = sandbox.working_directory

        session = GrpcSession(
            container_ip=sandbox.grpc_host,
            grpc_port=sandbox.grpc_port,
            session_id=f"{user_id}:{chat_id}",
            model=self._model,
            working_directory=working_directory,
        )

        try:
            await session.start(prompt)
        except Exception as exc:
            log.exception("[Dispatcher] Falha ao iniciar gRPC para task %s", task_id[:8])
            await self._update_task_status(task_id, "error")
            await self._insert_error_event(task_id, str(exc))
            await session.close()
            return

        # Actualiza session_id no DB
        if self._pool:
            await self._pool.execute(
                "UPDATE agent_tasks SET session_id=$1 WHERE id=$2::uuid",
                f"{user_id}:{chat_id}",
                task_id,
            )

        runner = TaskRunner(task_id=task_id, session=session, db_url=self._db_url)
        self._runners[task_id] = runner
        await runner.start()
        log.info("[Dispatcher] TaskRunner started for task %s", task_id[:8])

    async def _reconnect_orphaned_tasks(self) -> None:
        """Marca como error tasks que ficaram running/paused após restart.

        Não tenta reconectar streams gRPC (o openclaude já perdeu o contexto);
        insere um evento de erro para que a UI saiba que a task foi interrompida.
        """
        if not self._pool:
            return
        rows = await self._pool.fetch(
            "SELECT id FROM agent_tasks WHERE status IN ('running','paused')"
        )
        for row in rows:
            task_id = str(row["id"])
            await self._update_task_status(task_id, "error")
            await self._insert_error_event(
                task_id,
                "Serviço reiniciado — sessão interrompida. Envie uma nova mensagem para continuar.",
            )
            log.warning("[Dispatcher] Orphan task %s marked as error", task_id[:8])

    async def _insert_task(
        self,
        task_id: str,
        conversation_id: str | None,
        prompt: str,
        triggered_by: str,
        trigger_payload: dict,
    ) -> None:
        if not self._pool:
            return
        await self._pool.execute(
            """
            INSERT INTO agent_tasks
                (id, conversation_id, env_slug, prompt, triggered_by, trigger_payload)
            VALUES
                ($1::uuid, $2::uuid, $3, $4, $5, $6::jsonb)
            """,
            task_id,
            conversation_id,
            "default",
            prompt,
            triggered_by,
            json.dumps(trigger_payload),
        )

    async def _update_task_status(self, task_id: str, status: str) -> None:
        if not self._pool:
            return
        await self._pool.execute(
            "UPDATE agent_tasks SET status=$1, last_event_at=NOW() WHERE id=$2::uuid",
            status,
            task_id,
        )

    async def _insert_error_event(self, task_id: str, message: str) -> None:
        if not self._pool:
            return
        await self._pool.execute(
            "INSERT INTO agent_events (task_id, event_type, data) VALUES ($1::uuid, 'error', $2::jsonb)",
            task_id,
            json.dumps({"message": message}),
        )
