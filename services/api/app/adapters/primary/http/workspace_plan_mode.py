"""Modo de planejamento por workspace.

O modo ``plan`` é para quem vai programar: o agente investiga a fundo e escreve
um plano antes de responder. Em workspace de consulta isso só deixa a resposta
lenta, então o super admin liga o modo workspace a workspace.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.value_objects import DEFAULT_PERMISSION_MODE, PermissionMode
from app.infrastructure.orm_models_workspaces import Workspace


async def allowed_permission_mode(
    session: AsyncSession, workspace_id: uuid.UUID | None, mode: str | None
) -> str | None:
    """Troca ``plan`` pelo modo padrão quando o workspace não o habilita.

    Conversa sem workspace (legado, por repositório) segue como estava.
    """
    if mode != PermissionMode.PLAN.value or workspace_id is None:
        return mode
    enabled = await session.scalar(
        select(Workspace.plan_mode_enabled).where(Workspace.id == workspace_id)
    )
    return mode if enabled else DEFAULT_PERMISSION_MODE
