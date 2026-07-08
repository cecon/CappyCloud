"""Use cases for per-user persisted preferences."""

from __future__ import annotations

import uuid

from app.domain.entities import UserPreferences
from app.domain.value_objects import DEFAULT_PERMISSION_MODE, validate_permission_mode
from app.ports.user_preferences import UserPreferencesRepository


class GetUserPreferences:
    def __init__(self, preferences: UserPreferencesRepository) -> None:
        self._preferences = preferences

    async def execute(self, user_id: uuid.UUID) -> UserPreferences:
        prefs = await self._preferences.get(user_id)
        if prefs is not None:
            return prefs
        return UserPreferences(
            user_id=user_id,
            default_permission_mode=DEFAULT_PERMISSION_MODE,
        )


class UpdateUserPreferences:
    def __init__(self, preferences: UserPreferencesRepository) -> None:
        self._preferences = preferences

    async def execute(
        self,
        user_id: uuid.UUID,
        *,
        default_permission_mode: str | None = None,
    ) -> UserPreferences:
        current = await self._preferences.get(user_id)
        mode = (
            validate_permission_mode(default_permission_mode)
            if default_permission_mode is not None
            else (current.default_permission_mode if current else DEFAULT_PERMISSION_MODE)
        )
        return await self._preferences.upsert(
            UserPreferences(user_id=user_id, default_permission_mode=mode)
        )
