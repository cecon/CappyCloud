"""HTTP endpoint com o histórico de ações do agente por turno da conversa.

Os eventos de cada execução já ficam em ``agent_events``; aqui eles são
compactados (texto contíguo unido, saídas truncadas) e associados à mensagem
do utilizador que disparou o turno, para o chat reconstruir a timeline depois
de recarregar a página.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import get_authenticated_user, get_db_session
from app.domain.entities import User, UserRole

router = APIRouter(prefix="/conversations", tags=["conversations"])

ACTIVITY_EVENT_TYPES = (
    "text",
    "tool_start",
    "tool_result",
    "command_start",
    "command_result",
    "status",
    "action_required",
    "error",
    "done",
    "canceled",
    "stalled",
    "permission_timeout",
)
MAX_FIELD_CHARS = 4000
MAX_EVENTS_PER_TURN = 1500


@router.get("/{conversation_id}/activity")
async def get_conversation_activity(
    conversation_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[dict]:
    """Turnos do agente com eventos compactados, na ordem da conversa."""
    owner_row = await db.execute(
        text("SELECT user_id FROM conversations WHERE id = :cid"),
        {"cid": str(conversation_id)},
    )
    owner = owner_row.fetchone()
    if not owner or (owner.user_id != current.id and current.role is not UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada")

    tasks = (
        await db.execute(
            text(
                "SELECT id, status, model_used, created_at, started_at, completed_at, "
                "last_event_at FROM agent_tasks WHERE conversation_id = :cid "
                "ORDER BY created_at"
            ),
            {"cid": str(conversation_id)},
        )
    ).fetchall()
    if not tasks:
        return []

    user_messages = (
        await db.execute(
            text(
                "SELECT id, created_at FROM messages "
                "WHERE conversation_id = :cid AND role = 'user' ORDER BY created_at"
            ),
            {"cid": str(conversation_id)},
        )
    ).fetchall()

    events = (
        await db.execute(
            text(
                "SELECT task_id, event_type, data, created_at FROM agent_events "
                "WHERE task_id = ANY(:tids) AND event_type = ANY(:types) ORDER BY id"
            ),
            {"tids": [t.id for t in tasks], "types": list(ACTIVITY_EVENT_TYPES)},
        )
    ).fetchall()

    events_by_task: dict[Any, list[dict]] = {t.id: [] for t in tasks}
    for row in events:
        data = row.data if isinstance(row.data, dict) else json.loads(row.data or "{}")
        events_by_task[row.task_id].append(
            {"type": row.event_type, "data": data, "at": row.created_at}
        )

    owners = assign_turns_to_messages(
        [t.created_at for t in tasks], [m.created_at for m in user_messages]
    )
    return [
        {
            "task_id": str(task.id),
            "user_message_id": str(user_messages[idx].id) if idx is not None else None,
            "status": task.status,
            "model_used": task.model_used,
            "created_at": task.created_at.isoformat(),
            "completed_at": _iso(task.completed_at),
            "last_event_at": _iso(task.last_event_at),
            "events": compact_events(events_by_task[task.id]),
        }
        for task, idx in zip(tasks, owners, strict=True)
    ]


def assign_turns_to_messages(
    task_times: list[datetime], message_times: list[datetime]
) -> list[int | None]:
    """Associa cada task à última mensagem do utilizador criada antes dela.

    A mensagem é gravada antes de a task ser despachada, então a mensagem
    "dona" de um turno é a mais recente com ``created_at <= task.created_at``.
    """
    owners: list[int | None] = []
    msg_idx = -1
    for task_time in task_times:
        while msg_idx + 1 < len(message_times) and message_times[msg_idx + 1] <= task_time:
            msg_idx += 1
        owners.append(msg_idx if msg_idx >= 0 else None)
    return owners


def compact_events(events: list[dict]) -> list[dict]:
    """Une texto contíguo e trunca campos grandes, mantendo a ordem original."""
    compacted: list[dict] = []
    for event in events:
        event_type = event["type"]
        data = dict(event.get("data") or {})
        at = _iso(event.get("at"))
        if event_type == "status" and not data.get("stage"):
            continue
        if event_type == "text":
            content = str(data.get("content") or "")
            if not content:
                continue
            if compacted and compacted[-1]["type"] == "text":
                compacted[-1]["data"]["content"] += content
                continue
            data = {"content": content}
        for key in ("input", "output", "details_markdown", "content"):
            value = data.get(key)
            if isinstance(value, str) and len(value) > MAX_FIELD_CHARS and event_type != "text":
                data[key] = value[:MAX_FIELD_CHARS] + "\n… (truncado)"
        compacted.append({"type": event_type, "data": data, "at": at})
    if len(compacted) > MAX_EVENTS_PER_TURN:
        # Mantém o desfecho (done/error) mesmo quando o turno é muito longo.
        compacted = compacted[: MAX_EVENTS_PER_TURN - 1] + compacted[-1:]
    return compacted


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
