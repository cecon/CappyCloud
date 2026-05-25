"""TaskRunner launch sequence for TaskDispatcher."""

from __future__ import annotations

import logging

from ._evidence_prefetch import inject_evidence_prefetch
from ._grpc_session import GrpcSession
from ._pipeline_helpers import (
    build_prompt_with_worktree_context,
    resolve_model_provider_runtime_config,
)
from ._task_events import (
    insert_error_event,
    insert_status_event,
    update_task_status,
)
from ._task_runner import TaskRunner
from ._worktree_validation import validate_and_inject_worktree

log = logging.getLogger(__name__)


async def launch_runner(
    dispatcher,
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
    """Cria sessão, inicia gRPC e registra o runner ativo."""
    user_id = conversation_id or "system"
    chat_id = conversation_id or task_id

    try:
        lease = await dispatcher._env_manager.get_or_create_session(
            user_id=user_id,
            chat_id=chat_id,
            repos=repos or [],
            session_root=session_root,
            sandbox_id=sandbox_id,
        )
        sandbox = lease.record
        emit_session_progress = lease.created
        if emit_session_progress:
            await _emit_session_ready(dispatcher, task_id, sandbox, repos)
    except Exception as exc:
        log.exception("[Dispatcher] Falha ao criar sessão para task %s", task_id[:8])
        await update_task_status(dispatcher._pool, task_id, "error")
        await insert_error_event(dispatcher._pool, task_id, str(exc))
        return

    working_directory = sandbox.working_directory
    if repos and len(repos) == 1 and repos[0].get("worktree_path"):
        working_directory = repos[0]["worktree_path"]
    log.debug(
        "[Dispatcher] working_directory=%r for task %s", working_directory, task_id[:8]
    )

    user_prompt = prompt
    sandbox_session_url = f"http://{sandbox.grpc_host}:8080"
    prompt = await build_prompt_with_worktree_context(
        prompt,
        sandbox_session_url,
        repos or [],
        session_root or sandbox.session_root,
    )

    if sandbox_session_url and repos:
        new_prompt = await validate_and_inject_worktree(
            pool=dispatcher._pool,
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

    prompt = await inject_evidence_prefetch(
        prompt,
        user_message=user_prompt,
        sandbox_session_url=sandbox_session_url,
        repos=repos or [],
        session_root=session_root or sandbox.session_root,
    )

    effective_model = override_model or dispatcher._model
    provider_config = await resolve_model_provider_runtime_config(
        dispatcher._db_url,
        effective_model,
    )
    session = GrpcSession(
        container_ip=sandbox.grpc_host,
        grpc_port=sandbox.grpc_port,
        session_id=f"{user_id}:{chat_id}",
        model=effective_model,
        working_directory=working_directory,
        provider_base_url=provider_config.base_url if provider_config else "",
        provider_api_key=provider_config.api_key if provider_config else "",
        provider_api_format=provider_config.api_format if provider_config else "",
    )

    if emit_session_progress:
        await insert_status_event(
            dispatcher._pool,
            task_id,
            "Aguardando resposta do agente.",
            "agent",
            "initializing",
            state="active",
        )
    try:
        await session.start(prompt, attachments=attachments)
    except Exception as exc:
        log.exception("[Dispatcher] Falha ao iniciar gRPC para task %s", task_id[:8])
        await update_task_status(dispatcher._pool, task_id, "error")
        await insert_error_event(dispatcher._pool, task_id, str(exc))
        await session.close()
        return

    if dispatcher._pool:
        await dispatcher._pool.execute(
            "UPDATE agent_tasks SET session_id=$1 WHERE id=$2::uuid",
            f"{user_id}:{chat_id}",
            task_id,
        )

    runner = TaskRunner(
        task_id=task_id,
        session=session,
        db_url=dispatcher._db_url,
        model_used=effective_model,
        conversation_id=conversation_id,
        emit_session_progress=emit_session_progress,
    )
    dispatcher._runners[task_id] = runner
    await runner.start()
    log.info("[Dispatcher] TaskRunner started for task %s", task_id[:8])


async def _emit_session_ready(
    dispatcher, task_id: str, sandbox, repos: list | None
) -> None:
    await insert_status_event(
        dispatcher._pool,
        task_id,
        "Sessão do agente preparada.",
        "session",
        "initializing",
    )
    if repos:
        repo_slugs = ", ".join(
            str(repo.get("slug") or repo.get("alias") or "?") for repo in repos
        )
        await insert_status_event(
            dispatcher._pool,
            task_id,
            f"Repositório preparado: {repo_slugs}.",
            "repository",
            "initializing",
        )
    await insert_status_event(
        dispatcher._pool,
        task_id,
        f"Sessão criada em {sandbox.working_directory}",
        "ready",
        "initializing",
    )
