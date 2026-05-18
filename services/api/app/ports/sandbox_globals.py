"""Ports — SandboxSkillRepository e SandboxAgentRepository (ADR-004 §6).

Espelham o shape do que o openclaude espera dentro do container:
- Skill: pasta ``~/.claude/skills/<name>/SKILL.md`` com markdown.
- Agent: arquivo ``~/.claude/agents/<name>.md`` com frontmatter YAML.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.domain.entities import SandboxAgent, SandboxSkill


class SandboxSkillRepository(ABC):
    @abstractmethod
    async def list_for_sandbox(self, sandbox_id: uuid.UUID) -> list[SandboxSkill]:
        """Devolve skills da sandbox em ordem cronológica (ativas e inativas)."""

    @abstractmethod
    async def get(self, skill_id: uuid.UUID, sandbox_id: uuid.UUID) -> SandboxSkill | None:
        """Devolve skill por id, verificando que pertence à sandbox."""

    @abstractmethod
    async def get_by_name(self, name: str, sandbox_id: uuid.UUID) -> SandboxSkill | None:
        """Devolve skill pelo nome único dentro da sandbox."""

    @abstractmethod
    async def create(self, skill: SandboxSkill) -> SandboxSkill:
        """Persiste nova skill."""

    @abstractmethod
    async def update(self, skill: SandboxSkill) -> SandboxSkill:
        """Atualiza skill existente."""

    @abstractmethod
    async def delete(self, skill_id: uuid.UUID, sandbox_id: uuid.UUID) -> bool:
        """Remove skill. ``True`` se apagou, ``False`` se não existia."""


class SandboxAgentRepository(ABC):
    @abstractmethod
    async def list_for_sandbox(self, sandbox_id: uuid.UUID) -> list[SandboxAgent]:
        """Devolve agents da sandbox em ordem cronológica."""

    @abstractmethod
    async def get(self, agent_id: uuid.UUID, sandbox_id: uuid.UUID) -> SandboxAgent | None:
        """Devolve agent por id, verificando que pertence à sandbox."""

    @abstractmethod
    async def get_by_name(self, name: str, sandbox_id: uuid.UUID) -> SandboxAgent | None:
        """Devolve agent pelo nome único dentro da sandbox."""

    @abstractmethod
    async def create(self, agent: SandboxAgent) -> SandboxAgent:
        """Persiste novo agent."""

    @abstractmethod
    async def update(self, agent: SandboxAgent) -> SandboxAgent:
        """Atualiza agent existente."""

    @abstractmethod
    async def delete(self, agent_id: uuid.UUID, sandbox_id: uuid.UUID) -> bool:
        """Remove agent. ``True`` se apagou, ``False`` se não existia."""
