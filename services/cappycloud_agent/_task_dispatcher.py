"""TaskDispatcher — orquestra o ciclo de vida das AgentTasks."""

from __future__ import annotations

import asyncio
import logging
import uuid

import asyncpg

from ._agent_context import (
    fetch_worktree_top_levels,
    inject_section_before_user_message,
    render_worktree_top_level_section,
)
from ._environment_manager import EnvironmentManager
from ._grpc_session import GrpcSession
from ._orphan_recovery import reconnect_orphaned_tasks
from ._session_store import SessionStore
from ._task_events import (
    insert_error_event,
    insert_status_event,
    insert_task,
    update_task_status,
)
from ._task_runner import TaskRunner
from ._worktree_validation import validate_and_inject_worktree

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
                attachments=attachments,
            ),
            name=f"dispatch-{task_id[:8]}",
        )
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
        user_id = conversation_id or "system"
        chat_id = conversation_id or task_id

        try:
            lease = await self._env_manager.get_or_create_session(
                user_id=user_id,
                chat_id=chat_id,
                repos=repos or [],
                session_root=session_root,
                sandbox_id=sandbox_id,
            )
            sandbox = lease.record
            mode = "initializing" if lease.created else "resuming"
            session_message = "Sessão criada" if lease.created else "Sessão retomada"
            repository_message = (
                "Repositório preparado" if lease.created else "Repositório sincronizado"
            )
            await insert_status_event(
                self._pool, task_id, "Sessão do agente preparada.", "session", mode
            )
            if repos:
                repo_slugs = ", ".join(
                    str(repo.get("slug") or repo.get("alias") or "?") for repo in repos
                )
                await insert_status_event(
                    self._pool,
                    task_id,
                    f"{repository_message}: {repo_slugs}.",
                    "repository",
                    mode,
                )
            await insert_status_event(
                self._pool,
                task_id,
                f"{session_message} em {sandbox.working_directory}",
                "ready",
                mode,
            )
        except Exception as exc:
            log.exception("[Dispatcher] Falha ao criar sessão para task %s", task_id[:8])
            await update_task_status(self._pool, task_id, "error")
            await insert_error_event(self._pool, task_id, str(exc))
            return

        # Derive working_directory from pipeline repos (authoritative, come from
        # the main DB) rather than from the stored session record, which may be
        # stale (e.g. created before worktree_path was tracked).
        working_directory = sandbox.working_directory
        if repos and len(repos) == 1 and repos[0].get("worktree_path"):
            working_directory = repos[0]["worktree_path"]
        log.debug(
            "[Dispatcher] working_directory=%r for task %s", working_directory, task_id[:8]
        )

        # Materializa um snapshot barato do worktree no prompt. Isso evita que
        # modelos menores respondam "pasta vazia" sem consultar o repositório.
        sandbox_session_url = f"http://{sandbox.grpc_host}:8080"
        if repos:
            try:
                top_level = await fetch_worktree_top_levels(
                    sandbox_session_url,
                    repos,
                    session_root or sandbox.session_root,
                )
                section = render_worktree_top_level_section(top_level)
                if section:
                    prompt = inject_section_before_user_message(prompt, section)
            except Exception as exc:  # noqa: BLE001 - degrada graciosamente
                log.warning("[Dispatcher] worktree top-level fetch falhou: %s", exc)

        # Validamos worktree ANTES do gRPC: openclaude com wd inexistente
        # devolve `done` vazio (erro genérico). Falha cedo com causa específica.
        if sandbox_session_url and repos:
            new_prompt = await validate_and_inject_worktree(
                pool=self._pool,
                task_id=task_id,
                prompt=prompt,
                repos=repos,
                sandbox_session_url=sandbox_session_url,
                session_root=session_root,
                working_directory=working_directory,
            )
            if new_prompt is None:
                return
            prompt = new_prompt

        session = GrpcSession(
            container_ip=sandbox.grpc_host,
            grpc_port=sandbox.grpc_port,
            session_id=f"{user_id}:{chat_id}",
            model=override_model or self._model,
            working_directory=working_directory,
        )

        # stage='agent' é emitido pelo TaskRunner quando o LLM responder de
        # facto (primeiro chunk/tool). Evita "tudo verde + erro logo a seguir".
        try:
            await session.start(prompt, attachments=attachments)
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
        await reconnect_orphaned_tasks(self._pool)
