"""In-memory fakes para entidades de sandbox (ADR-004).

Mantido em arquivo próprio para que ``conftest.py`` não cresça além do
limite do projeto (300 linhas). Os testes importam via ``tests.conftest``
graças aos re-exports.
"""

from __future__ import annotations

import uuid
from dataclasses import replace

from app.domain.entities import (
    ContainerStatus,
    GlobalSkill,
    Sandbox,
    SandboxAgent,
    SandboxSkill,
)
from app.ports.repositories import SandboxRepository
from app.ports.sandbox_bootstrap import SandboxBootstrapGateway
from app.ports.sandbox_globals import SandboxAgentRepository, SandboxSkillRepository
from app.ports.sandbox_runtime import (
    RuntimeFailureError,
    RuntimeProbe,
    SandboxRuntimeGateway,
)

from tests.fakes_mcp import (
    InMemoryMcpRepository as InMemoryMcpRepository,
)
from tests.fakes_mcp import (
    InMemoryUserMcpServerRepository as InMemoryUserMcpServerRepository,
)


class FakeRuntimeGateway(SandboxRuntimeGateway):
    """Fake controlável para testar transições de status sem Docker."""

    def __init__(
        self,
        *,
        ensure_status: ContainerStatus = ContainerStatus.RUNNING,
        stop_status: ContainerStatus = ContainerStatus.STOPPED,
        fail_on: str | None = None,
    ) -> None:
        self.ensure_status = ensure_status
        self.stop_status = stop_status
        self.fail_on = fail_on
        self.calls: list[str] = []

    async def ensure_service(self, sandbox: Sandbox) -> RuntimeProbe:
        self.calls.append("ensure")
        if self.fail_on == "ensure":
            raise RuntimeFailureError("Boom", sandbox_id=sandbox.id)
        return RuntimeProbe(status=self.ensure_status, runtime_ref="fake-cid")

    async def stop(self, sandbox: Sandbox) -> RuntimeProbe:
        self.calls.append("stop")
        if self.fail_on == "stop":
            raise RuntimeFailureError("Boom", sandbox_id=sandbox.id)
        return RuntimeProbe(status=self.stop_status, runtime_ref="fake-cid")

    async def status(self, sandbox: Sandbox) -> RuntimeProbe:
        return RuntimeProbe(status=self.ensure_status, runtime_ref="fake-cid")

    async def remove(self, sandbox: Sandbox) -> None:
        self.calls.append("remove")


class FakeSandboxBootstrap(SandboxBootstrapGateway):
    """Bootstrap fake — captura as chamadas para asserts em testes, sem Docker."""

    def __init__(self) -> None:
        self.calls: list[tuple[uuid.UUID, dict]] = []
        self.claude_calls: list[tuple[uuid.UUID, str]] = []
        self.skill_calls: list[tuple[uuid.UUID, list]] = []
        self.agent_calls: list[tuple[uuid.UUID, list]] = []

    async def write_claude_md(self, sandbox: Sandbox) -> None:
        self.claude_calls.append((sandbox.id, sandbox.claude_md))

    async def write_settings_json(self, sandbox: Sandbox, settings: dict) -> None:
        self.calls.append((sandbox.id, settings))

    async def write_skills(self, sandbox: Sandbox, skills: list[SandboxSkill]) -> None:
        self.skill_calls.append((sandbox.id, list(skills)))

    async def write_agents(self, sandbox: Sandbox, agents: list[SandboxAgent]) -> None:
        self.agent_calls.append((sandbox.id, list(agents)))


class InMemorySandboxSkillRepository(SandboxSkillRepository):
    def __init__(self) -> None:
        self._store: dict[uuid.UUID, GlobalSkill] = {}
        self._assignments: dict[uuid.UUID, set[uuid.UUID]] = {}

    async def list_for_sandbox(self, sandbox_id: uuid.UUID) -> list[SandboxSkill]:
        rows = [
            self._to_sandbox_skill(s, sandbox_id)
            for s in self._store.values()
            if sandbox_id in self._assignments.get(s.id, set())
        ]
        return sorted(rows, key=lambda s: s.created_at)

    async def list_global(self) -> list[GlobalSkill]:
        rows = [
            GlobalSkill(
                id=s.id,
                name=s.name,
                description=s.description,
                content=s.content,
                enabled=s.enabled,
                sandbox_ids=list(self._assignments.get(s.id, set())),
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
            for s in self._store.values()
        ]
        return sorted(rows, key=lambda s: s.created_at)

    async def get_global(self, skill_id: uuid.UUID) -> GlobalSkill | None:
        sk = self._store.get(skill_id)
        if sk is None:
            return None
        return GlobalSkill(
            id=sk.id,
            name=sk.name,
            description=sk.description,
            content=sk.content,
            enabled=sk.enabled,
            sandbox_ids=list(self._assignments.get(sk.id, set())),
            created_at=sk.created_at,
            updated_at=sk.updated_at,
        )

    async def get_global_by_name(self, name: str) -> GlobalSkill | None:
        for sk in self._store.values():
            if sk.name == name:
                return await self.get_global(sk.id)
        return None

    async def create_global(self, skill: GlobalSkill, sandbox_ids: list[uuid.UUID]) -> GlobalSkill:
        self._store[skill.id] = skill
        self._assignments[skill.id] = set(sandbox_ids)
        return (await self.get_global(skill.id)) or skill

    async def update_global(self, skill: GlobalSkill, sandbox_ids: list[uuid.UUID]) -> GlobalSkill:
        if skill.id not in self._store:
            raise ValueError(f"GlobalSkill {skill.id} not found")
        self._store[skill.id] = skill
        self._assignments[skill.id] = set(sandbox_ids)
        return (await self.get_global(skill.id)) or skill

    async def delete_global(self, skill_id: uuid.UUID) -> bool:
        if skill_id not in self._store:
            return False
        del self._store[skill_id]
        self._assignments.pop(skill_id, None)
        return True

    async def get(self, skill_id: uuid.UUID, sandbox_id: uuid.UUID) -> SandboxSkill | None:
        sk = self._store.get(skill_id)
        if sk is None or sandbox_id not in self._assignments.get(skill_id, set()):
            return None
        return self._to_sandbox_skill(sk, sandbox_id)

    async def get_by_name(self, name: str, sandbox_id: uuid.UUID) -> SandboxSkill | None:
        for sk in self._store.values():
            if sk.name == name and sandbox_id in self._assignments.get(sk.id, set()):
                return self._to_sandbox_skill(sk, sandbox_id)
        return None

    async def create(self, skill: SandboxSkill) -> SandboxSkill:
        created = await self.create_global(
            GlobalSkill(
                id=skill.id,
                name=skill.name,
                description=skill.description,
                content=skill.content,
                enabled=skill.enabled,
                created_at=skill.created_at,
                updated_at=skill.updated_at,
            ),
            [skill.sandbox_id],
        )
        return self._to_sandbox_skill(created, skill.sandbox_id)

    async def update(self, skill: SandboxSkill) -> SandboxSkill:
        if skill.id not in self._store:
            raise ValueError(f"SandboxSkill {skill.id} not found")
        current = self._store[skill.id]
        updated = GlobalSkill(
            id=skill.id,
            name=skill.name,
            description=skill.description,
            content=skill.content,
            enabled=skill.enabled,
            created_at=current.created_at,
            updated_at=skill.updated_at,
        )
        self._store[skill.id] = updated
        self._assignments.setdefault(skill.id, set()).add(skill.sandbox_id)
        return self._to_sandbox_skill(updated, skill.sandbox_id)

    async def delete(self, skill_id: uuid.UUID, sandbox_id: uuid.UUID) -> bool:
        sk = self._store.get(skill_id)
        if sk is None or sandbox_id not in self._assignments.get(skill_id, set()):
            return False
        self._assignments[skill_id].discard(sandbox_id)
        if not self._assignments[skill_id]:
            del self._store[skill_id]
            del self._assignments[skill_id]
        return True

    @staticmethod
    def _to_sandbox_skill(skill: GlobalSkill, sandbox_id: uuid.UUID) -> SandboxSkill:
        return SandboxSkill(
            id=skill.id,
            sandbox_id=sandbox_id,
            name=skill.name,
            description=skill.description,
            content=skill.content,
            enabled=skill.enabled,
            created_at=skill.created_at,
            updated_at=skill.updated_at,
        )


class InMemorySandboxAgentRepository(SandboxAgentRepository):
    def __init__(self) -> None:
        self._store: dict[uuid.UUID, SandboxAgent] = {}

    async def list_for_sandbox(self, sandbox_id: uuid.UUID) -> list[SandboxAgent]:
        rows = [a for a in self._store.values() if a.sandbox_id == sandbox_id]
        return sorted(rows, key=lambda a: a.created_at)

    async def get(self, agent_id: uuid.UUID, sandbox_id: uuid.UUID) -> SandboxAgent | None:
        ag = self._store.get(agent_id)
        if ag is None or ag.sandbox_id != sandbox_id:
            return None
        return ag

    async def get_by_name(self, name: str, sandbox_id: uuid.UUID) -> SandboxAgent | None:
        return next(
            (a for a in self._store.values() if a.sandbox_id == sandbox_id and a.name == name),
            None,
        )

    async def create(self, agent: SandboxAgent) -> SandboxAgent:
        self._store[agent.id] = agent
        return agent

    async def update(self, agent: SandboxAgent) -> SandboxAgent:
        if agent.id not in self._store:
            raise ValueError(f"SandboxAgent {agent.id} not found")
        self._store[agent.id] = agent
        return agent

    async def delete(self, agent_id: uuid.UUID, sandbox_id: uuid.UUID) -> bool:
        ag = self._store.get(agent_id)
        if ag is None or ag.sandbox_id != sandbox_id:
            return False
        del self._store[agent_id]
        return True


class InMemorySandboxRepository(SandboxRepository):
    """In-memory sandbox store for testing (ADR-004)."""

    def __init__(self) -> None:
        self._store: dict[uuid.UUID, Sandbox] = {}

    async def list_all(self) -> list[Sandbox]:
        return sorted(self._store.values(), key=lambda s: s.created_at)

    async def get(self, sandbox_id: uuid.UUID) -> Sandbox | None:
        return self._store.get(sandbox_id)

    async def get_by_name(self, name: str) -> Sandbox | None:
        return next((s for s in self._store.values() if s.name == name), None)

    async def save(self, sandbox: Sandbox) -> Sandbox:
        self._store[sandbox.id] = sandbox
        return sandbox

    async def update(self, sandbox: Sandbox) -> Sandbox:
        if sandbox.id not in self._store:
            raise LookupError(f"Sandbox {sandbox.id} não encontrada.")
        self._store[sandbox.id] = sandbox
        return sandbox

    async def update_container_status(
        self, sandbox_id: uuid.UUID, status: ContainerStatus
    ) -> Sandbox | None:
        current = self._store.get(sandbox_id)
        if current is None:
            return None
        updated = replace(current, container_status=status)
        self._store[sandbox_id] = updated
        return updated

    async def delete(self, sandbox_id: uuid.UUID) -> bool:
        return self._store.pop(sandbox_id, None) is not None
