"""SQLAlchemy adapter for user preferences."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import UserPreferences as UserPreferencesEntity
from app.domain.value_objects import validate_permission_mode
from app.infrastructure.orm_models_user_preferences import UserPreferences as UserPreferencesORM
from app.ports.user_preferences import UserPreferencesRepository


class SQLAlchemyUserPreferencesRepository(UserPreferencesRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: uuid.UUID) -> UserPreferencesEntity | None:
        row = await self._session.get(UserPreferencesORM, user_id)
        return self._to_entity(row) if row else None

    async def upsert(self, preferences: UserPreferencesEntity) -> UserPreferencesEntity:
        row = await self._session.get(UserPreferencesORM, preferences.user_id)
        mode = validate_permission_mode(preferences.default_permission_mode)
        if row is None:
            row = UserPreferencesORM(
                user_id=preferences.user_id,
                default_permission_mode=mode,
            )
            self._session.add(row)
        else:
            row.default_permission_mode = mode
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_entity(row)

    @staticmethod
    def _to_entity(row: UserPreferencesORM) -> UserPreferencesEntity:
        return UserPreferencesEntity(
            user_id=row.user_id,
            default_permission_mode=validate_permission_mode(row.default_permission_mode),
        )
