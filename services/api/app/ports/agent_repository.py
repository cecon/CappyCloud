"""Port — AgentRepository ABC.

Desacopla o use case CreateConversation do ORM, permitindo fakes em testes.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod


class AgentRepository(ABC):
    @abstractmethod
    async def get_default_id(self) -> uuid.UUID | None:
        """Retorna o UUID do agente marcado como is_default, ou None."""

    @abstractmethod
    async def can_user_access(self, user_id: uuid.UUID, agent_id: uuid.UUID) -> bool:
        """True se o agente é público (owner_id IS NULL) ou pertence ao user."""
