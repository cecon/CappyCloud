"""SQLAlchemy adapters para SandboxSkillRepository e SandboxAgentRepository."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import (
    GlobalSkill as GlobalSkillEntity,
)
from app.domain.entities import (
    SandboxAgent as SandboxAgentEntity,
)
from app.domain.entities import (
    SandboxSkill as SandboxSkillEntity,
)
from app.infrastructure.orm_models_sandbox_globals import (
    GlobalSkill as GlobalSkillORM,
)
from app.infrastructure.orm_models_sandbox_globals import (
    GlobalSkillSandbox as GlobalSkillSandboxORM,
)
from app.infrastructure.orm_models_sandbox_globals import (
    SandboxAgent as SandboxAgentORM,
)
from app.infrastructure.orm_models_sandbox_globals import (
    SandboxSkill as SandboxSkillORM,
)
from app.ports.sandbox_globals import SandboxAgentRepository, SandboxSkillRepository


class SQLAlchemySandboxSkillRepository(SandboxSkillRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_sandbox(self, sandbox_id: uuid.UUID) -> list[SandboxSkillEntity]:
        rows = await self._session.execute(
            select(GlobalSkillORM)
            .join(
                GlobalSkillSandboxORM,
                GlobalSkillSandboxORM.skill_id == GlobalSkillORM.id,
            )
            .where(GlobalSkillSandboxORM.sandbox_id == sandbox_id)
            .order_by(GlobalSkillORM.created_at)
        )
        global_rows = [self._to_sandbox_entity(r, sandbox_id) for r in rows.scalars()]

        legacy_rows = await self._session.execute(
            select(SandboxSkillORM)
            .where(SandboxSkillORM.sandbox_id == sandbox_id)
            .order_by(SandboxSkillORM.created_at)
        )
        return global_rows + [self._legacy_to_entity(r) for r in legacy_rows.scalars()]

    async def list_global(self) -> list[GlobalSkillEntity]:
        rows = (
            (
                await self._session.execute(
                    select(GlobalSkillORM).order_by(GlobalSkillORM.created_at)
                )
            )
            .scalars()
            .all()
        )
        sandbox_rows = (
            (
                await self._session.execute(
                    select(GlobalSkillSandboxORM).order_by(GlobalSkillSandboxORM.created_at)
                )
            )
            .scalars()
            .all()
        )
        by_skill: dict[uuid.UUID, list[uuid.UUID]] = {}
        for row in sandbox_rows:
            by_skill.setdefault(row.skill_id, []).append(row.sandbox_id)
        return [self._to_global_entity(row, by_skill.get(row.id, [])) for row in rows]

    async def get_global(self, skill_id: uuid.UUID) -> GlobalSkillEntity | None:
        row = await self._session.get(GlobalSkillORM, skill_id)
        if row is None:
            return None
        sandbox_rows = (
            (
                await self._session.execute(
                    select(GlobalSkillSandboxORM)
                    .where(GlobalSkillSandboxORM.skill_id == skill_id)
                    .order_by(GlobalSkillSandboxORM.created_at)
                )
            )
            .scalars()
            .all()
        )
        return self._to_global_entity(row, [item.sandbox_id for item in sandbox_rows])

    async def get_global_by_name(self, name: str) -> GlobalSkillEntity | None:
        row = await self._session.scalar(select(GlobalSkillORM).where(GlobalSkillORM.name == name))
        if row is None:
            return None
        return await self.get_global(row.id)

    async def create_global(
        self, skill: GlobalSkillEntity, sandbox_ids: list[uuid.UUID]
    ) -> GlobalSkillEntity:
        orm = GlobalSkillORM(
            id=skill.id,
            name=skill.name,
            description=skill.description,
            content=skill.content,
            enabled=skill.enabled,
        )
        self._session.add(orm)
        for sandbox_id in dict.fromkeys(sandbox_ids):
            self._session.add(GlobalSkillSandboxORM(skill_id=skill.id, sandbox_id=sandbox_id))
        await self._session.commit()
        await self._session.refresh(orm)
        return self._to_global_entity(orm, list(dict.fromkeys(sandbox_ids)))

    async def update_global(
        self, skill: GlobalSkillEntity, sandbox_ids: list[uuid.UUID]
    ) -> GlobalSkillEntity:
        orm = await self._session.get(GlobalSkillORM, skill.id)
        if orm is None:
            raise ValueError(f"GlobalSkill {skill.id} not found")
        orm.name = skill.name
        orm.description = skill.description
        orm.content = skill.content
        orm.enabled = skill.enabled
        await self._session.execute(
            delete(GlobalSkillSandboxORM).where(GlobalSkillSandboxORM.skill_id == skill.id)
        )
        unique_sandbox_ids = list(dict.fromkeys(sandbox_ids))
        for sandbox_id in unique_sandbox_ids:
            self._session.add(GlobalSkillSandboxORM(skill_id=skill.id, sandbox_id=sandbox_id))
        await self._session.commit()
        await self._session.refresh(orm)
        return self._to_global_entity(orm, unique_sandbox_ids)

    async def delete_global(self, skill_id: uuid.UUID) -> bool:
        result: CursorResult = await self._session.execute(  # type: ignore[assignment]
            delete(GlobalSkillORM).where(GlobalSkillORM.id == skill_id)
        )
        await self._session.commit()
        return result.rowcount > 0

    async def get(self, skill_id: uuid.UUID, sandbox_id: uuid.UUID) -> SandboxSkillEntity | None:
        global_row = await self._session.scalar(
            select(GlobalSkillORM)
            .join(
                GlobalSkillSandboxORM,
                GlobalSkillSandboxORM.skill_id == GlobalSkillORM.id,
            )
            .where(
                GlobalSkillORM.id == skill_id,
                GlobalSkillSandboxORM.sandbox_id == sandbox_id,
            )
        )
        if global_row is not None:
            return self._to_sandbox_entity(global_row, sandbox_id)
        legacy = await self._session.get(SandboxSkillORM, skill_id)
        if not legacy or legacy.sandbox_id != sandbox_id:
            return None
        return self._legacy_to_entity(legacy)

    async def get_by_name(self, name: str, sandbox_id: uuid.UUID) -> SandboxSkillEntity | None:
        global_row = await self._session.scalar(
            select(GlobalSkillORM)
            .join(
                GlobalSkillSandboxORM,
                GlobalSkillSandboxORM.skill_id == GlobalSkillORM.id,
            )
            .where(
                GlobalSkillSandboxORM.sandbox_id == sandbox_id,
                GlobalSkillORM.name == name,
            )
        )
        if global_row is not None:
            return self._to_sandbox_entity(global_row, sandbox_id)
        row = await self._session.scalar(
            select(SandboxSkillORM).where(
                SandboxSkillORM.sandbox_id == sandbox_id,
                SandboxSkillORM.name == name,
            )
        )
        return self._legacy_to_entity(row) if row else None

    async def create(self, skill: SandboxSkillEntity) -> SandboxSkillEntity:
        created = await self.create_global(
            GlobalSkillEntity(
                id=skill.id,
                name=skill.name,
                description=skill.description,
                content=skill.content,
                enabled=skill.enabled,
            ),
            [skill.sandbox_id],
        )
        return self._to_sandbox_entity_from_global(created, skill.sandbox_id)

    async def _create_legacy(self, skill: SandboxSkillEntity) -> SandboxSkillEntity:
        orm = SandboxSkillORM(
            id=skill.id,
            sandbox_id=skill.sandbox_id,
            name=skill.name,
            description=skill.description,
            content=skill.content,
            enabled=skill.enabled,
        )
        self._session.add(orm)
        await self._session.commit()
        await self._session.refresh(orm)
        return self._legacy_to_entity(orm)

    async def update(self, skill: SandboxSkillEntity) -> SandboxSkillEntity:
        orm = await self._session.get(GlobalSkillORM, skill.id)
        if orm is not None:
            assignment_rows = (
                (
                    await self._session.execute(
                        select(GlobalSkillSandboxORM)
                        .where(GlobalSkillSandboxORM.skill_id == skill.id)
                        .order_by(GlobalSkillSandboxORM.created_at)
                    )
                )
                .scalars()
                .all()
            )
            sandbox_ids = [row.sandbox_id for row in assignment_rows]
            if skill.sandbox_id not in sandbox_ids:
                sandbox_ids.append(skill.sandbox_id)
            updated = await self.update_global(
                GlobalSkillEntity(
                    id=skill.id,
                    name=skill.name,
                    description=skill.description,
                    content=skill.content,
                    enabled=skill.enabled,
                ),
                sandbox_ids,
            )
            return self._to_sandbox_entity_from_global(updated, skill.sandbox_id)

        legacy = await self._session.get(SandboxSkillORM, skill.id)
        if not legacy or legacy.sandbox_id != skill.sandbox_id:
            raise ValueError(f"SandboxSkill {skill.id} not found for sandbox {skill.sandbox_id}")
        legacy.name = skill.name
        legacy.description = skill.description
        legacy.content = skill.content
        legacy.enabled = skill.enabled
        await self._session.commit()
        await self._session.refresh(legacy)
        return self._legacy_to_entity(legacy)

    async def delete(self, skill_id: uuid.UUID, sandbox_id: uuid.UUID) -> bool:
        result: CursorResult = await self._session.execute(  # type: ignore[assignment]
            delete(GlobalSkillSandboxORM).where(
                GlobalSkillSandboxORM.skill_id == skill_id,
                GlobalSkillSandboxORM.sandbox_id == sandbox_id,
            )
        )
        if result.rowcount > 0:
            remaining = await self._session.scalar(
                select(GlobalSkillSandboxORM).where(GlobalSkillSandboxORM.skill_id == skill_id)
            )
            if remaining is None:
                await self._session.execute(
                    delete(GlobalSkillORM).where(GlobalSkillORM.id == skill_id)
                )
            await self._session.commit()
            return True

        legacy_result: CursorResult = await self._session.execute(  # type: ignore[assignment]
            delete(SandboxSkillORM).where(
                SandboxSkillORM.id == skill_id,
                SandboxSkillORM.sandbox_id == sandbox_id,
            )
        )
        await self._session.commit()
        return legacy_result.rowcount > 0

    @staticmethod
    def _to_global_entity(
        orm: GlobalSkillORM, sandbox_ids: list[uuid.UUID]
    ) -> GlobalSkillEntity:
        return GlobalSkillEntity(
            id=orm.id,
            name=orm.name,
            description=orm.description or "",
            content=orm.content or "",
            enabled=orm.enabled,
            sandbox_ids=list(sandbox_ids),
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    @staticmethod
    def _to_sandbox_entity(orm: GlobalSkillORM, sandbox_id: uuid.UUID) -> SandboxSkillEntity:
        return SandboxSkillEntity(
            id=orm.id,
            sandbox_id=sandbox_id,
            name=orm.name,
            description=orm.description or "",
            content=orm.content or "",
            enabled=orm.enabled,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    @staticmethod
    def _to_sandbox_entity_from_global(
        skill: GlobalSkillEntity, sandbox_id: uuid.UUID
    ) -> SandboxSkillEntity:
        return SandboxSkillEntity(
            id=skill.id,
            sandbox_id=sandbox_id,
            name=skill.name,
            description=skill.description,
            content=skill.content,
            enabled=skill.enabled,
            created_at=skill.created_at,
            updated_at=skill.updated_at,
        )

    @staticmethod
    def _legacy_to_entity(orm: SandboxSkillORM) -> SandboxSkillEntity:
        return SandboxSkillEntity(
            id=orm.id,
            sandbox_id=orm.sandbox_id,
            name=orm.name,
            description=orm.description or "",
            content=orm.content or "",
            enabled=orm.enabled,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )


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
