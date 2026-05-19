"""SQLAlchemy implementation of UserRepository port."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import User as UserEntity
from app.domain.entities import UserRole
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
            role=user.role.value,
            is_super_admin=user.is_super_admin,
            must_change_password=user.must_change_password,
        )
        self._session.add(orm)
        await self._session.commit()
        await self._session.refresh(orm)
        return self._to_entity(orm)

    async def list_all(self) -> list[UserEntity]:
        result = await self._session.execute(select(UserORM).order_by(UserORM.created_at.asc()))
        return [self._to_entity(row) for row in result.scalars().all()]

    async def update_role(self, user_id: uuid.UUID, role: UserRole) -> UserEntity | None:
        row = await self._session.get(UserORM, user_id)
        if row is None:
            return None
        row.role = role.value
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_entity(row)

    async def update_password(
        self,
        user_id: uuid.UUID,
        hashed_password: str,
        *,
        must_change_password: bool,
    ) -> UserEntity | None:
        row = await self._session.get(UserORM, user_id)
        if row is None:
            return None
        row.hashed_password = hashed_password
        row.must_change_password = must_change_password
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_entity(row)

    @staticmethod
    def _to_entity(row: UserORM) -> UserEntity:
        return UserEntity(
            id=row.id,
            email=row.email,
            hashed_password=row.hashed_password,
            role=_role_from_str(row.role),
            is_super_admin=bool(row.is_super_admin),
            must_change_password=bool(row.must_change_password),
            created_at=row.created_at,
        )


def _role_from_str(value: str | None) -> UserRole:
    """Mapeia o texto persistido para o enum, com fallback defensivo para USER.

    Linhas pré-migração ou casos exóticos (texto fora do enum) caem em USER —
    nunca elevam silenciosamente para ADMIN.
    """
    if value is None:
        return UserRole.USER
    try:
        return UserRole(value)
    except ValueError:
        return UserRole.USER
