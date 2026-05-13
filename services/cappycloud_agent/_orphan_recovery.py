"""Recovery de tasks órfãs após restart do serviço.

Tasks que estavam ``running``/``paused`` no momento do restart perdem o seu
TaskRunner em memória — precisam ser marcadas como ``error`` para o utilizador
saber que tem de reenviar a mensagem.
"""

from __future__ import annotations

import logging

import asyncpg

from ._task_events import insert_error_event, update_task_status

log = logging.getLogger(__name__)

_RESTART_MSG = "Serviço reiniciado — sessão interrompida. Envie nova mensagem."


async def reconnect_orphaned_tasks(pool: asyncpg.Pool | None) -> None:
    """Marca como ``error`` todas as tasks ainda ``running``/``paused``."""
    if pool is None:
        return
    rows = await pool.fetch(
        "SELECT id FROM agent_tasks WHERE status IN ('running','paused')"
    )
    for row in rows:
        task_id = str(row["id"])
        await update_task_status(pool, task_id, "error")
        await insert_error_event(pool, task_id, _RESTART_MSG)
        log.warning("[Dispatcher] Orphan task %s as error", task_id[:8])
