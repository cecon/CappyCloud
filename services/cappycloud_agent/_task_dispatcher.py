"""TaskDispatcher — orquestra o ciclo de vida das AgentTasks."""

from __future__ import annotations

import asyncio
import logging
import uuid

import asyncpg  # type: ignore

from ._agent_context import (
    fetch_worktree_top_levels,
    inject_section_before_user_message,
    render_worktree_top_level_section,
)
from ._environment_manager import EnvironmentManager
from ._grpc_session import GrpcSession
from ._session_store import SessionStore
from ._task_events import (
    insert_error_event,
    insert_status_event,
    insert_task,
    update_task_status,
)
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
        # conversation_id → task_id (only alive runners)
        self._conv_to_task: dict[str, str] = {}

    async def start(self) -> None:
        """Conecta ao DB e reconecta tasks órfãs de um restart anterior."""
        self._pool = await asyncpg.create_pool(self._db_url, min_size=1, max_size=5)
        await self._reconnect_orphaned_tasks()

    async def stop(self) -> None:
        for runner in list(self._runners.values()):
            await runner.close()
        self._runners.clear()
        self._conv_to_task.clear()
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
    ) -> str:
        """Cria uma agent_task e arranca o runner; retorna o task_id (UUID)."""
        task_id = str(uuid.uuid4())
        await insert_task(
            self._pool,
            task_id,
            conversation_id,
            prompt,
            triggered_by,
            trigger_payload or {},
        )
        if conversation_id:
            self._conv_to_task[conversation_id] = task_id
        asyncio.create_task(
            self._launch_runner(
                task_id,
                prompt,
                conversation_id,
                repos=repos or [],
                session_root=session_root,
                sandbox_id=sandbox_id,
                override_model=override_model,
                sandbox_session_url=sandbox_session_url,
            ),
            name=f"dispatch-{task_id[:8]}",
        )
        return task_id

    def get_runner(self, task_id: str) -> TaskRunner | None:
        return self._runners.get(task_id)

    def get_runner_for_conversation(self, conversation_id: str) -> TaskRunner | None:
        """Retorna o runner activo da conversa (status running ou paused)."""
        task_id = self._conv_to_task.get(conversation_id)
        if task_id:
            runner = self._runners.get(task_id)
            if runner and runner.is_alive():
                return runner
            # Runner morreu — limpa o mapa
            self._conv_to_task.pop(conversation_id, None)
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

    async def send_message(self, task_id: str, message: str) -> bool:
        """Envia nova mensagem numa task running (nova turn)."""
        runner = self._runners.get(task_id)
        if runner and runner.is_alive() and not runner.pending_action:
            await runner.send_message(message)
            return True
        return False

    async def cancel_task(self, task_id: str) -> bool:
        """Cancela uma task em execução."""
        runner = self._runners.pop(task_id, None)
        if runner:
            await runner.close()
        # Limpa o mapa conv→task para esta task
        for conv_id, tid in list(self._conv_to_task.items()):
            if tid == task_id:
                self._conv_to_task.pop(conv_id, None)
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
        # Limpa entradas do conv→task que apontam para runners mortos
        for conv_id, tid in list(self._conv_to_task.items()):
            if tid in dead or tid not in self._runners:
                self._conv_to_task.pop(conv_id, None)
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
    ) -> None:
        """Cria a sessão, inicia a GrpcSession e arranca o TaskRunner."""
        user_id = conversation_id or "system"
        chat_id = conversation_id or task_id

        mode = "initializing"

        try:
            repo_slugs = ", ".join(str(r.get("slug") or r.get("alias") or "?") for r in repos) if repos else ""
            if repo_slugs:
                await insert_status_event(self._pool, task_id, f"Preparando: {repo_slugs}", "indexing_start", mode)

            lease = await self._env_manager.get_or_create_session(
                user_id=user_id, chat_id=chat_id, repos=repos or [],
                session_root=session_root, sandbox_id=sandbox_id,
            )
            sandbox = lease.record
            mode = "initializing" if lease.created else "resuming"
            await insert_status_event(self._pool, task_id, "Sessão preparada.", "session", mode)

            if repo_slugs:
                msg = "Repositório preparado" if lease.created else "Repositório sincronizado"
                await insert_status_event(self._pool, task_id, f"{msg}: {repo_slugs}.", "repository", mode)
                await insert_status_event(self._pool, task_id, f"Repositórios prontos: {repo_slugs}", "indexing_ready", mode)

            msg_sess = "Sessão criada" if lease.created else "Sessão retomada"
            await insert_status_event(self._pool, task_id, f"{msg_sess} em {sandbox.working_directory}", "ready", mode)
        except Exception as exc:
            log.exception("[Dispatcher] Falha ao criar sessão para task %s", task_id[:8])
            await update_task_status(self._pool, task_id, "error")
            await insert_error_event(self._pool, task_id, str(exc))
            return

        working_directory = sandbox.working_directory

        # Worktree(s) já materializados — enriquecemos o prompt com o
        # snapshot top-level. Crítico para modelos pequenos (ex.: gpt-oss-120b)
        # que sem isso fazem grep cego com globs errados e desistem.
        if sandbox_session_url and repos:
            try:
                top_level = await fetch_worktree_top_levels(
                    sandbox_session_url, repos, session_root
                )
                section = render_worktree_top_level_section(top_level)
                if section:
                    prompt = inject_section_before_user_message(prompt, section)
                log.info("[Dispatcher] Prompt length after worktree injection: %d chars", len(prompt))
            except Exception as exc:  # noqa: BLE001 — degrada graciosamente
                log.warning("[Dispatcher] worktree top-level fetch falhou: %s", exc)

        session = GrpcSession(
            container_ip=sandbox.grpc_host,
            grpc_port=sandbox.grpc_port,
            session_id=f"{user_id}:{chat_id}",
            model=override_model or self._model,
            working_directory=working_directory,
        )

        try:
            await insert_status_event(
                self._pool, task_id, "Iniciando agente...", "agent", mode
            )
            await session.start(prompt)
        except Exception as exc:
            log.exception("[Dispatcher] Falha ao iniciar gRPC para task %s", task_id[:8])
            await update_task_status(self._pool, task_id, "error")
            await insert_error_event(self._pool, task_id, str(exc))
            await session.close()
            return

        if self._pool:
            await self._pool.execute(
                "UPDATE agent_tasks SET session_id=$1 WHERE id=$2::uuid",
                f"{user_id}:{chat_id}",
                task_id,
            )

        runner = TaskRunner(
            task_id=task_id,
            session=session,
            db_url=self._db_url,
            model_used=override_model or self._model,
        )
        self._runners[task_id] = runner
        await runner.start()
        log.info("[Dispatcher] TaskRunner started for task %s", task_id[:8])

    async def _reconnect_orphaned_tasks(self) -> None:
        """Marca como error as tasks running/paused remanescentes após restart."""
        if not self._pool:
            return
        rows = await self._pool.fetch(
            "SELECT id FROM agent_tasks WHERE status IN ('running','paused')"
        )
        for row in rows:
            task_id = str(row["id"])
            await update_task_status(self._pool, task_id, "error")
            await insert_error_event(
                self._pool,
                task_id,
                "Serviço reiniciado — sessão interrompida. Envie nova mensagem.",
            )
            log.warning("[Dispatcher] Orphan task %s marked as error", task_id[:8])
