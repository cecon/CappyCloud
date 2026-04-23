"""SQLAlchemy implementation of RepositoryRepository port.

Lookup-only: este adapter cobre apenas as opera\u00e7\u00f5es necess\u00e1rias para que
use cases resolvam ``slug \u2192 id`` (ex.: ``CreateConversation``). O CRUD
completo da tabela ``repositories`` continua a viver no router admin
(``adapters/primary/http/repositories_admin.py``).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Repository as RepositoryEntity
from app.infrastructure.orm_models import Repository as RepositoryORM
from app.ports.repositories import RepositoryRepository


class SQLAlchemyRepositoryRepository(RepositoryRepository):
    """Concrete RepositoryRepository backed by PostgreSQL via SQLAlchemy async."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, repo_id: uuid.UUID) -> RepositoryEntity | None:
        row = await self._session.get(RepositoryORM, repo_id)
        return self._to_entity(row) if row else None

    async def get_by_slug(self, slug: str) -> RepositoryEntity | None:
        result = await self._session.execute(
            select(RepositoryORM).where(RepositoryORM.slug == slug)
        )
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    @staticmethod
    def _to_entity(row: RepositoryORM) -> RepositoryEntity:
        return RepositoryEntity(
            id=row.id,
            slug=row.slug,
            name=row.name,
            clone_url=row.clone_url,
            default_branch=row.default_branch,
            provider_id=row.provider_id,
            sandbox_id=row.sandbox_id,
            sandbox_status=row.sandbox_status,
            sandbox_path=row.sandbox_path,
            last_sync_at=row.last_sync_at,
            error_message=row.error_message,
            active=row.active,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
