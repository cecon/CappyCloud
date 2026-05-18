"""SSE event streaming helpers for Pipeline."""

from __future__ import annotations

import asyncio
import json
import queue
from collections.abc import Generator

import asyncpg

from ._pipeline_helpers import sse


def stream_task_events(
    *,
    loop: asyncio.AbstractEventLoop,
    database_url: str,
    task_id: str,
    cursor: int | None,
) -> Generator[str, None, None]:
    out_q: queue.Queue = queue.Queue()

    async def _produce() -> None:
        pool = await asyncpg.create_pool(database_url, min_size=1, max_size=2)
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
                        task_id,
                        last_id,
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

    asyncio.run_coroutine_threadsafe(_produce(), loop)

    while True:
        item = out_q.get(timeout=310)
        if item is None:
            break
        event_type, data, eid = item
        yield sse({"type": event_type, "cursor": eid, **(data if data else {})})
