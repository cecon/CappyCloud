"""SQLAlchemy implementation for user agent profile lookup."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.orm_models import UserAgentProfile
from app.ports.repositories import UserAgentProfileRepository


class SQLAlchemyUserAgentProfileRepository(UserAgentProfileRepository):
    """Resolve o agente padrão associado ao utilizador autenticado."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_default_agent_id(self, user_id: uuid.UUID) -> uuid.UUID | None:
        row = await self._session.scalar(
            select(UserAgentProfile)
            .where(UserAgentProfile.user_id == user_id)
            .where(UserAgentProfile.is_default.is_(True))
            .order_by(UserAgentProfile.updated_at.desc(), UserAgentProfile.created_at.desc())
            .limit(1)
        )
        return row.agent_id if row else None
