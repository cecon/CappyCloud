"""Use cases — gestão administrativa de skills e agents globais por sandbox.

ADR-004 §6. Camada pura: sem FastAPI nem SQLAlchemy. Caller (HTTP) cobra
as permissões de leitura/administração.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.domain.entities import GlobalSkill, SandboxAgent, SandboxSkill
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


class ListGlobalSkills:
    def __init__(self, repo: SandboxSkillRepository) -> None:
        self._repo = repo

    async def execute(self) -> list[GlobalSkill]:
        return await self._repo.list_global()


class CreateGlobalSkill:
    def __init__(self, repo: SandboxSkillRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        *,
        name: str,
        description: str = "",
        content: str = "",
        enabled: bool = True,
        sandbox_ids: list[uuid.UUID] | None = None,
    ) -> GlobalSkill:
        normalised = name.strip()
        if not normalised:
            raise ValueError("Nome da skill é obrigatório.")
        if await self._repo.get_global_by_name(normalised):
            raise SandboxGlobalNameTakenError(f"Skill global '{normalised}' já existe.")
        skill = GlobalSkill(
            id=uuid.uuid4(),
            name=normalised,
            description=description,
            content=content,
            enabled=enabled,
        )
        return await self._repo.create_global(skill, list(sandbox_ids or []))


class UpdateGlobalSkill:
    def __init__(self, repo: SandboxSkillRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        *,
        skill_id: uuid.UUID,
        name: str,
        description: str,
        content: str,
        enabled: bool,
        sandbox_ids: list[uuid.UUID],
    ) -> GlobalSkill:
        skill = await self._repo.get_global(skill_id)
        if not skill:
            raise SandboxGlobalNotFoundError(f"Skill global {skill_id} não encontrada.")
        normalised = name.strip()
        if not normalised:
            raise ValueError("Nome da skill é obrigatório.")
        if skill.name != normalised:
            existing = await self._repo.get_global_by_name(normalised)
            if existing:
                raise SandboxGlobalNameTakenError(f"Skill global '{normalised}' já existe.")
        skill.name = normalised
        skill.description = description
        skill.content = content
        skill.enabled = enabled
        skill.updated_at = datetime.now(UTC)
        return await self._repo.update_global(skill, sandbox_ids)


class DeleteGlobalSkill:
    def __init__(self, repo: SandboxSkillRepository) -> None:
        self._repo = repo

    async def execute(self, skill_id: uuid.UUID) -> bool:
        return await self._repo.delete_global(skill_id)


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
        if await self._repo.get_global_by_name(normalised):
            raise SandboxGlobalNameTakenError(f"Skill global '{normalised}' já existe.")
        skill = GlobalSkill(
            id=uuid.uuid4(),
            name=normalised,
            description=description,
            content=content,
            enabled=enabled,
        )
        created = await self._repo.create_global(skill, [sandbox_id])
        return SandboxSkill(
            id=created.id,
            sandbox_id=sandbox_id,
            name=created.name,
            description=created.description,
            content=created.content,
            enabled=created.enabled,
            created_at=created.created_at,
            updated_at=created.updated_at,
        )


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
            existing = await self._repo.get_global_by_name(normalised)
            if existing:
                raise SandboxGlobalNameTakenError(f"Skill global '{normalised}' já existe.")
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
