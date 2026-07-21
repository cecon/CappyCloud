"""Ports for CappyCloud-authorized model profile lookups."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.domain.entities import UserRole


@dataclass(frozen=True)
class AuthorizedModelProfile:
    model_id: str
    display_name: str
    provider: str
    active: bool
    provider_active: bool
    capabilities: list[str]
    context_window: int
    max_output_tokens: int | None = None
    input_cost_per_1m_usd: float | None = None
    output_cost_per_1m_usd: float | None = None
    unavailable_reason: str | None = None


class ModelProfileLookupPort(ABC):
    """Lookup model profiles that may be shown or selected by the user."""

    @abstractmethod
    async def list_for_user(
        self, user_id: uuid.UUID, role: UserRole
    ) -> list[AuthorizedModelProfile]:
        """Return active and explanatory inactive profiles visible to the user."""
