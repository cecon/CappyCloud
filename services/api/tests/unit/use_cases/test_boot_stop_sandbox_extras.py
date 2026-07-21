"""Additional BootSandbox / StopSandbox coverage kept below file-size limits."""

from __future__ import annotations

import pytest
from app.application.use_cases.admin_sandboxes import StopSandbox
from app.domain.entities import ContainerStatus, SandboxRuntime
from app.ports.sandbox_runtime import RuntimeFailureError

from tests.conftest import (
    FakeRuntimeGateway,
    FakeSandboxBootstrap,
    InMemoryMcpRepository,
    InMemorySandboxAgentRepository,
    InMemorySandboxRepository,
    InMemorySandboxSkillRepository,
)
from tests.unit.use_cases.test_boot_stop_sandbox import _boot_uc, _make


@pytest.fixture
def repo() -> InMemorySandboxRepository:
    return InMemorySandboxRepository()


@pytest.fixture
def runtime() -> FakeRuntimeGateway:
    return FakeRuntimeGateway()


@pytest.fixture
def mcps() -> InMemoryMcpRepository:
    return InMemoryMcpRepository()


@pytest.fixture
def skills() -> InMemorySandboxSkillRepository:
    return InMemorySandboxSkillRepository()


@pytest.fixture
def agents() -> InMemorySandboxAgentRepository:
    return InMemorySandboxAgentRepository()


@pytest.fixture
def bootstrap() -> FakeSandboxBootstrap:
    return FakeSandboxBootstrap()


class TestBootSandboxExtras:
    async def test_boot_passes_skills_and_agents_to_bootstrap(
        self,
        repo: InMemorySandboxRepository,
        runtime: FakeRuntimeGateway,
        bootstrap: FakeSandboxBootstrap,
        mcps: InMemoryMcpRepository,
        skills: InMemorySandboxSkillRepository,
        agents: InMemorySandboxAgentRepository,
    ) -> None:
        from app.application.use_cases.sandbox_globals import (
            CreateSandboxAgent,
            CreateSandboxSkill,
        )

        sandbox = await _make(repo, name="alpha")
        await CreateSandboxSkill(skills).execute(
            sandbox_id=sandbox.id,
            name="naming-conventions",
            description="Convencoes de nomenclatura do CappyCloud.",
            content="# Naming\nUse snake_case em Python, camelCase em TS.",
            enabled=True,
        )
        await CreateSandboxAgent(agents).execute(
            sandbox_id=sandbox.id,
            name="reviewer",
            description="Revisor de PRs.",
            system_prompt="Voce e um revisor critico de codigo.",
            model="claude-sonnet-4-6",
            tools=["Read", "Grep"],
            enabled=True,
        )

        await _boot_uc(
            repo,
            {SandboxRuntime.COMPOSE: runtime},
            {SandboxRuntime.COMPOSE: bootstrap},
            mcps,
            skills,
            agents,
        ).execute(sandbox.id)

        assert len(bootstrap.skill_calls) == 1
        _, called_skills = bootstrap.skill_calls[0]
        assert [s.name for s in called_skills] == ["naming-conventions"]
        assert called_skills[0].content.startswith("# Naming")

        assert len(bootstrap.agent_calls) == 1
        _, called_agents = bootstrap.agent_calls[0]
        assert [a_.name for a_ in called_agents] == ["reviewer"]
        assert called_agents[0].tools == ["Read", "Grep"]
        assert called_agents[0].model == "claude-sonnet-4-6"


class TestStopSandbox:
    async def test_stop_marks_stopped(
        self,
        repo: InMemorySandboxRepository,
        runtime: FakeRuntimeGateway,
    ) -> None:
        sandbox = await _make(repo, name="alpha")
        await repo.update_container_status(sandbox.id, ContainerStatus.RUNNING)

        result = await StopSandbox(repo, {SandboxRuntime.COMPOSE: runtime}).execute(sandbox.id)

        assert result.container_status is ContainerStatus.STOPPED
        assert runtime.calls == ["stop"]

    async def test_stop_propagates_failure_and_marks_error(
        self,
        repo: InMemorySandboxRepository,
    ) -> None:
        sandbox = await _make(repo, name="alpha")
        runtime = FakeRuntimeGateway(fail_on="stop")
        with pytest.raises(RuntimeFailureError):
            await StopSandbox(repo, {SandboxRuntime.COMPOSE: runtime}).execute(sandbox.id)
        stored = await repo.get(sandbox.id)
        assert stored is not None
        assert stored.container_status is ContainerStatus.ERROR
