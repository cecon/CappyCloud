"""Ports for per-user persisted preferences."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.domain.entities import UserPreferences


class UserPreferencesRepository(ABC):
    @abstractmethod
    async def get(self, user_id: uuid.UUID) -> UserPreferences | None:
        """Return preferences for ``user_id`` when they exist."""

    @abstractmethod
    async def upsert(self, preferences: UserPreferences) -> UserPreferences:
        """Create or update preferences for ``user_id``."""
