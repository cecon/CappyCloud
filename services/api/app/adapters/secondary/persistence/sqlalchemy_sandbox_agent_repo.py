"""SQLAlchemy adapter for sandbox global agents."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import SandboxAgent as SandboxAgentEntity
from app.infrastructure.orm_models_sandbox_globals import (
    SandboxAgent as SandboxAgentORM,
)
from app.ports.sandbox_globals import SandboxAgentRepository


class SQLAlchemySandboxAgentRepository(SandboxAgentRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_sandbox(self, sandbox_id: uuid.UUID) -> list[SandboxAgentEntity]:
        rows = await self._session.execute(
            select(SandboxAgentORM)
            .where(SandboxAgentORM.sandbox_id == sandbox_id)
            .order_by(SandboxAgentORM.created_at)
        )
        return [self._to_entity(r) for r in rows.scalars()]

    async def get(self, agent_id: uuid.UUID, sandbox_id: uuid.UUID) -> SandboxAgentEntity | None:
        row = await self._session.get(SandboxAgentORM, agent_id)
        if not row or row.sandbox_id != sandbox_id:
            return None
        return self._to_entity(row)

    async def get_by_name(self, name: str, sandbox_id: uuid.UUID) -> SandboxAgentEntity | None:
        row = await self._session.scalar(
            select(SandboxAgentORM).where(
                SandboxAgentORM.sandbox_id == sandbox_id,
                SandboxAgentORM.name == name,
            )
        )
        return self._to_entity(row) if row else None

    async def create(self, agent: SandboxAgentEntity) -> SandboxAgentEntity:
        orm = SandboxAgentORM(
            id=agent.id,
            sandbox_id=agent.sandbox_id,
            name=agent.name,
            description=agent.description,
            system_prompt=agent.system_prompt,
            model=agent.model,
            tools=list(agent.tools),
            enabled=agent.enabled,
        )
        self._session.add(orm)
        await self._session.commit()
        await self._session.refresh(orm)
        return self._to_entity(orm)

    async def update(self, agent: SandboxAgentEntity) -> SandboxAgentEntity:
        orm = await self._session.get(SandboxAgentORM, agent.id)
        if not orm or orm.sandbox_id != agent.sandbox_id:
            raise ValueError(f"SandboxAgent {agent.id} not found for sandbox {agent.sandbox_id}")
        orm.name = agent.name
        orm.description = agent.description
        orm.system_prompt = agent.system_prompt
        orm.model = agent.model
        orm.tools = list(agent.tools)
        orm.enabled = agent.enabled
        await self._session.commit()
        await self._session.refresh(orm)
        return self._to_entity(orm)

    async def delete(self, agent_id: uuid.UUID, sandbox_id: uuid.UUID) -> bool:
        result: CursorResult = await self._session.execute(  # type: ignore[assignment]
            delete(SandboxAgentORM).where(
                SandboxAgentORM.id == agent_id,
                SandboxAgentORM.sandbox_id == sandbox_id,
            )
        )
        await self._session.commit()
        return result.rowcount > 0

    @staticmethod
    def _to_entity(orm: SandboxAgentORM) -> SandboxAgentEntity:
        return SandboxAgentEntity(
            id=orm.id,
            sandbox_id=orm.sandbox_id,
            name=orm.name,
            description=orm.description or "",
            system_prompt=orm.system_prompt or "",
            model=orm.model or "",
            tools=list(orm.tools or []),
            enabled=orm.enabled,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )
