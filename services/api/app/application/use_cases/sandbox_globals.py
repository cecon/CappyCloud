"""Use cases — gestão administrativa de skills e agents globais por sandbox.

ADR-004 §6. Camada pura: sem FastAPI nem SQLAlchemy. Caller (HTTP) cobra
``require_role(ADMIN)``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.domain.entities import SandboxAgent, SandboxSkill
from app.ports.sandbox_globals import SandboxAgentRepository, SandboxSkillRepository


class SandboxGlobalNotFoundError(Exception):
    """Skill ou agent solicitado não existe nesta sandbox."""


class SandboxGlobalNameTakenError(Exception):
    """Já existe item com este nome na sandbox."""


# ── Skills ───────────────────────────────────────────────────────────────────


class ListSandboxSkills:
    def __init__(self, repo: SandboxSkillRepository) -> None:
        self._repo = repo

    async def execute(self, sandbox_id: uuid.UUID) -> list[SandboxSkill]:
        return await self._repo.list_for_sandbox(sandbox_id)


class CreateSandboxSkill:
    def __init__(self, repo: SandboxSkillRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        *,
        sandbox_id: uuid.UUID,
        name: str,
        description: str = "",
        content: str = "",
        enabled: bool = True,
    ) -> SandboxSkill:
        normalised = name.strip()
        if not normalised:
            raise ValueError("Nome da skill é obrigatório.")
        if await self._repo.get_by_name(normalised, sandbox_id):
            raise SandboxGlobalNameTakenError(f"Skill '{normalised}' já existe nesta sandbox.")
        skill = SandboxSkill(
            id=uuid.uuid4(),
            sandbox_id=sandbox_id,
            name=normalised,
            description=description,
            content=content,
            enabled=enabled,
        )
        return await self._repo.create(skill)


class UpdateSandboxSkill:
    def __init__(self, repo: SandboxSkillRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        *,
        skill_id: uuid.UUID,
        sandbox_id: uuid.UUID,
        name: str,
        description: str,
        content: str,
        enabled: bool,
    ) -> SandboxSkill:
        skill = await self._repo.get(skill_id, sandbox_id)
        if not skill:
            raise SandboxGlobalNotFoundError(f"Skill {skill_id} não encontrada.")
        normalised = name.strip()
        if not normalised:
            raise ValueError("Nome da skill é obrigatório.")
        if skill.name != normalised:
            existing = await self._repo.get_by_name(normalised, sandbox_id)
            if existing:
                raise SandboxGlobalNameTakenError(f"Skill '{normalised}' já existe nesta sandbox.")
        skill.name = normalised
        skill.description = description
        skill.content = content
        skill.enabled = enabled
        skill.updated_at = datetime.now(UTC)
        return await self._repo.update(skill)


class DeleteSandboxSkill:
    def __init__(self, repo: SandboxSkillRepository) -> None:
        self._repo = repo

    async def execute(self, skill_id: uuid.UUID, sandbox_id: uuid.UUID) -> bool:
        return await self._repo.delete(skill_id, sandbox_id)


# ── Agents ───────────────────────────────────────────────────────────────────


class ListSandboxAgents:
    def __init__(self, repo: SandboxAgentRepository) -> None:
        self._repo = repo

    async def execute(self, sandbox_id: uuid.UUID) -> list[SandboxAgent]:
        return await self._repo.list_for_sandbox(sandbox_id)


class CreateSandboxAgent:
    def __init__(self, repo: SandboxAgentRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        *,
        sandbox_id: uuid.UUID,
        name: str,
        description: str = "",
        system_prompt: str = "",
        model: str = "",
        tools: list[str] | None = None,
        enabled: bool = True,
    ) -> SandboxAgent:
        normalised = name.strip()
        if not normalised:
            raise ValueError("Nome do agent é obrigatório.")
        if await self._repo.get_by_name(normalised, sandbox_id):
            raise SandboxGlobalNameTakenError(f"Agent '{normalised}' já existe nesta sandbox.")
        agent = SandboxAgent(
            id=uuid.uuid4(),
            sandbox_id=sandbox_id,
            name=normalised,
            description=description,
            system_prompt=system_prompt,
            model=model,
            tools=list(tools or []),
            enabled=enabled,
        )
        return await self._repo.create(agent)


class UpdateSandboxAgent:
    def __init__(self, repo: SandboxAgentRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        *,
        agent_id: uuid.UUID,
        sandbox_id: uuid.UUID,
        name: str,
        description: str,
        system_prompt: str,
        model: str,
        tools: list[str],
        enabled: bool,
    ) -> SandboxAgent:
        agent = await self._repo.get(agent_id, sandbox_id)
        if not agent:
            raise SandboxGlobalNotFoundError(f"Agent {agent_id} não encontrado.")
        normalised = name.strip()
        if not normalised:
            raise ValueError("Nome do agent é obrigatório.")
        if agent.name != normalised:
            existing = await self._repo.get_by_name(normalised, sandbox_id)
            if existing:
                raise SandboxGlobalNameTakenError(f"Agent '{normalised}' já existe nesta sandbox.")
        agent.name = normalised
        agent.description = description
        agent.system_prompt = system_prompt
        agent.model = model
        agent.tools = list(tools)
        agent.enabled = enabled
        agent.updated_at = datetime.now(UTC)
        return await self._repo.update(agent)


class DeleteSandboxAgent:
    def __init__(self, repo: SandboxAgentRepository) -> None:
        self._repo = repo

    async def execute(self, agent_id: uuid.UUID, sandbox_id: uuid.UUID) -> bool:
        return await self._repo.delete(agent_id, sandbox_id)
