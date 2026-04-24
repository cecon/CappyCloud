"""SQLAlchemy adapter para AgentRepository port."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.orm_models import Agent
from app.ports.agent_repository import AgentRepository


class SQLAlchemyAgentRepository(AgentRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_default_id(self) -> uuid.UUID | None:
        row = await self._session.scalar(
            select(Agent.id).where(Agent.is_default.is_(True), Agent.active.is_(True))
        )
        return row  # type: ignore[return-value]

    async def can_user_access(self, user_id: uuid.UUID, agent_id: uuid.UUID) -> bool:
        row = await self._session.scalar(
            select(Agent.id).where(
                Agent.id == agent_id,
                Agent.active.is_(True),
            )
        )
        if row is None:
            return False
        owner = await self._session.scalar(select(Agent.owner_id).where(Agent.id == agent_id))
        return owner is None or owner == user_id
