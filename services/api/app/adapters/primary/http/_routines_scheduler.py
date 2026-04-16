"""APScheduler helpers for routine schedule triggers."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request

    from app.adapters.primary.http.routines import RoutineIn

log = logging.getLogger(__name__)


def register_routine_schedules(request: Request, routine_id: str, body: RoutineIn) -> None:
    """Registra triggers do tipo 'schedule' no APScheduler."""
    try:
        scheduler = request.app.state.scheduler
    except AttributeError:
        return

    for t in body.triggers:
        if t.type != "schedule":
            continue
        cron_expr = t.config.get("cron", "")
        if not cron_expr:
            continue
        try:
            from apscheduler.triggers.cron import CronTrigger

            job_id = f"routine_{routine_id}_{cron_expr.replace(' ', '_')}"

            async def _run(
                rid: str = routine_id,
                prompt: str = body.prompt,
                env_slug: str = body.env_slug,
                _request: "Request" = request,
            ) -> None:
                from sqlalchemy import text

                from app.infrastructure.database import async_session_factory

                async with async_session_factory() as db_sess:
                    try:
                        agent = _request.app.state.agent
                        await agent.dispatch(
                            prompt=prompt,
                            env_slug=env_slug,
                            triggered_by="schedule",
                            trigger_payload={"routine_id": rid},
                        )
                        run_id = str(uuid.uuid4())
                        await db_sess.execute(
                            text(
                                "INSERT INTO routine_runs "
                                "(id, routine_id, triggered_by, status) "
                                "VALUES (:id, :rid, 'schedule', 'pending')"
                            ),
                            {"id": run_id, "rid": rid},
                        )
                        await db_sess.execute(
                            text("UPDATE routines SET last_run_at = NOW() WHERE id = :rid"),
                            {"rid": rid},
                        )
                        await db_sess.commit()
                    except Exception as exc:
                        log.error("Scheduled routine %s failed: %s", rid, exc)

            trigger = CronTrigger.from_crontab(cron_expr)
            scheduler.add_job(_run, trigger=trigger, id=job_id, replace_existing=True)
        except Exception as exc:
            log.error("Failed to register schedule for routine %s: %s", routine_id, exc)


def unregister_routine_schedules(request: Request, routine_id: str) -> None:
    """Remove todos os jobs do APScheduler para esta routine."""
    try:
        scheduler = request.app.state.scheduler
        for job in scheduler.get_jobs():
            if job.id.startswith(f"routine_{routine_id}_"):
                scheduler.remove_job(job.id)
    except Exception:
        pass
