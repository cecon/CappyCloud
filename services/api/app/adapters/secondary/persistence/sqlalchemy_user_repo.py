"""SQLAlchemy implementation of UserRepository port."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import User as UserEntity
from app.infrastructure.orm_models import User as UserORM
from app.ports.repositories import UserRepository


class SQLAlchemyUserRepository(UserRepository):
    """Concrete UserRepository backed by PostgreSQL via SQLAlchemy async."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> UserEntity | None:
        row = await self._session.get(UserORM, user_id)
        return self._to_entity(row) if row else None

    async def get_by_email(self, email: str) -> UserEntity | None:
        result = await self._session.execute(select(UserORM).where(UserORM.email == email))
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def save(self, user: UserEntity) -> UserEntity:
        orm = UserORM(
            id=user.id,
            email=user.email,
            hashed_password=user.hashed_password,
        )
        self._session.add(orm)
        await self._session.commit()
        await self._session.refresh(orm)
        return self._to_entity(orm)

    @staticmethod
    def _to_entity(row: UserORM) -> UserEntity:
        return UserEntity(
            id=row.id,
            email=row.email,
            hashed_password=row.hashed_password,
            created_at=row.created_at,
        )
