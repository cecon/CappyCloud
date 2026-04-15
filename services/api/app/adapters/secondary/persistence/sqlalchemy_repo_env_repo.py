"""SQLAlchemy implementation of RepoEnvironmentRepository port."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import RepoEnvironment as RepoEnvEntity
from app.infrastructure.orm_models import RepoEnvironment as RepoEnvORM
from app.ports.repositories import RepoEnvironmentRepository


class SQLAlchemyRepoEnvironmentRepository(RepoEnvironmentRepository):
    """Concrete RepoEnvironmentRepository backed by PostgreSQL via SQLAlchemy async."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> list[RepoEnvEntity]:
        result = await self._session.execute(select(RepoEnvORM).order_by(RepoEnvORM.name))
        return [self._to_entity(row) for row in result.scalars().all()]

    async def get(self, env_id: uuid.UUID) -> RepoEnvEntity | None:
        result = await self._session.execute(select(RepoEnvORM).where(RepoEnvORM.id == env_id))
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def get_by_slug(self, slug: str) -> RepoEnvEntity | None:
        result = await self._session.execute(select(RepoEnvORM).where(RepoEnvORM.slug == slug))
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def save(self, env: RepoEnvEntity) -> RepoEnvEntity:
        orm = RepoEnvORM(
            id=env.id,
            slug=env.slug,
            name=env.name,
            repo_url=env.repo_url,
            branch=env.branch,
        )
        self._session.add(orm)
        await self._session.commit()
        await self._session.refresh(orm)
        return self._to_entity(orm)

    async def delete(self, env_id: uuid.UUID) -> None:
        result = await self._session.execute(select(RepoEnvORM).where(RepoEnvORM.id == env_id))
        row = result.scalar_one_or_none()
        if row:
            await self._session.delete(row)
            await self._session.commit()

    @staticmethod
    def _to_entity(row: RepoEnvORM) -> RepoEnvEntity:
        return RepoEnvEntity(
            id=row.id,
            slug=row.slug,
            name=row.name,
            repo_url=row.repo_url,
            branch=row.branch,
            created_at=row.created_at,
        )
