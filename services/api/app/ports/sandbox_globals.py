"""Ports — SandboxSkillRepository e SandboxAgentRepository (ADR-004 §6).

Espelham o shape do que o openclaude espera dentro do container:
- Skill: pasta ``~/.claude/skills/<name>/SKILL.md`` com markdown.
- Agent: arquivo ``~/.claude/agents/<name>.md`` com frontmatter YAML.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.domain.entities import GlobalSkill, SandboxAgent, SandboxSkill


class SandboxSkillRepository(ABC):
    @abstractmethod
    async def list_for_sandbox(self, sandbox_id: uuid.UUID) -> list[SandboxSkill]:
        """Devolve skills globais atribuídas à sandbox em ordem cronológica."""

    @abstractmethod
    async def list_global(self) -> list[GlobalSkill]:
        """Devolve o catálogo global de skills."""

    @abstractmethod
    async def get_global(self, skill_id: uuid.UUID) -> GlobalSkill | None:
        """Devolve skill global por id."""

    @abstractmethod
    async def get_global_by_name(self, name: str) -> GlobalSkill | None:
        """Devolve skill global por nome único."""

    @abstractmethod
    async def create_global(self, skill: GlobalSkill, sandbox_ids: list[uuid.UUID]) -> GlobalSkill:
        """Persiste nova skill global e suas associações com sandboxes."""

    @abstractmethod
    async def update_global(self, skill: GlobalSkill, sandbox_ids: list[uuid.UUID]) -> GlobalSkill:
        """Atualiza skill global e substitui associações com sandboxes."""

    @abstractmethod
    async def delete_global(self, skill_id: uuid.UUID) -> bool:
        """Remove skill global e suas associações."""

    @abstractmethod
    async def get(self, skill_id: uuid.UUID, sandbox_id: uuid.UUID) -> SandboxSkill | None:
        """Devolve projeção da skill global, verificando associação com a sandbox."""

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
