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
    McpServer,
    Sandbox,
    SandboxAgent,
    SandboxSkill,
)
from app.ports.mcp_repository import McpServerRepository
from app.ports.repositories import SandboxRepository
from app.ports.sandbox_bootstrap import SandboxBootstrapGateway
from app.ports.sandbox_globals import SandboxAgentRepository, SandboxSkillRepository
from app.ports.sandbox_runtime import (
    RuntimeFailureError,
    RuntimeProbe,
    SandboxRuntimeGateway,
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


class InMemoryMcpRepository(McpServerRepository):
    """In-memory MCP store for testing (ADR-004 §6, por sandbox)."""

    def __init__(self) -> None:
        self._store: dict[uuid.UUID, McpServer] = {}

    async def list_for_sandbox(self, sandbox_id: uuid.UUID) -> list[McpServer]:
        rows = [m for m in self._store.values() if m.sandbox_id == sandbox_id]
        return sorted(rows, key=lambda m: m.created_at)

    async def get(self, mcp_id: uuid.UUID, sandbox_id: uuid.UUID) -> McpServer | None:
        mcp = self._store.get(mcp_id)
        if mcp is None or mcp.sandbox_id != sandbox_id:
            return None
        return mcp

    async def get_by_name(self, name: str, sandbox_id: uuid.UUID) -> McpServer | None:
        return next(
            (m for m in self._store.values() if m.sandbox_id == sandbox_id and m.name == name),
            None,
        )

    async def create(self, mcp: McpServer) -> McpServer:
        self._store[mcp.id] = mcp
        return mcp

    async def update(self, mcp: McpServer) -> McpServer:
        if mcp.id not in self._store:
            raise ValueError(f"McpServer {mcp.id} not found")
        self._store[mcp.id] = mcp
        return mcp

    async def delete(self, mcp_id: uuid.UUID, sandbox_id: uuid.UUID) -> bool:
        mcp = self._store.get(mcp_id)
        if mcp is None or mcp.sandbox_id != sandbox_id:
            return False
        del self._store[mcp_id]
        return True


class FakeSandboxBootstrap(SandboxBootstrapGateway):
    """Bootstrap fake — captura as chamadas para asserts em testes, sem Docker."""

    def __init__(self) -> None:
        self.calls: list[tuple[uuid.UUID, dict]] = []
        self.skill_calls: list[tuple[uuid.UUID, list]] = []
        self.agent_calls: list[tuple[uuid.UUID, list]] = []

    async def write_settings_json(self, sandbox: Sandbox, settings: dict) -> None:
        self.calls.append((sandbox.id, settings))

    async def write_skills(self, sandbox: Sandbox, skills: list[SandboxSkill]) -> None:
        self.skill_calls.append((sandbox.id, list(skills)))

    async def write_agents(self, sandbox: Sandbox, agents: list[SandboxAgent]) -> None:
        self.agent_calls.append((sandbox.id, list(agents)))


class InMemorySandboxSkillRepository(SandboxSkillRepository):
    def __init__(self) -> None:
        self._store: dict[uuid.UUID, SandboxSkill] = {}

    async def list_for_sandbox(self, sandbox_id: uuid.UUID) -> list[SandboxSkill]:
        rows = [s for s in self._store.values() if s.sandbox_id == sandbox_id]
        return sorted(rows, key=lambda s: s.created_at)

    async def get(self, skill_id: uuid.UUID, sandbox_id: uuid.UUID) -> SandboxSkill | None:
        sk = self._store.get(skill_id)
        if sk is None or sk.sandbox_id != sandbox_id:
            return None
        return sk

    async def get_by_name(self, name: str, sandbox_id: uuid.UUID) -> SandboxSkill | None:
        return next(
            (s for s in self._store.values() if s.sandbox_id == sandbox_id and s.name == name),
            None,
        )

    async def create(self, skill: SandboxSkill) -> SandboxSkill:
        self._store[skill.id] = skill
        return skill

    async def update(self, skill: SandboxSkill) -> SandboxSkill:
        if skill.id not in self._store:
            raise ValueError(f"SandboxSkill {skill.id} not found")
        self._store[skill.id] = skill
        return skill

    async def delete(self, skill_id: uuid.UUID, sandbox_id: uuid.UUID) -> bool:
        sk = self._store.get(skill_id)
        if sk is None or sk.sandbox_id != sandbox_id:
            return False
        del self._store[skill_id]
        return True


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
