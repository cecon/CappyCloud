"""Unit tests for BootSandbox / StopSandbox (ADR-004)."""

from __future__ import annotations

import uuid

import pytest
from app.application.use_cases.admin_sandboxes import (
    BootSandbox,
    CreateSandbox,
    SandboxNotFoundError,
    StopSandbox,
)
from app.domain.entities import ContainerStatus, Sandbox, SandboxRuntime
from app.ports.sandbox_runtime import RuntimeFailureError, SandboxRuntimeGateway

from tests.conftest import (
    FakeRuntimeGateway,
    FakeSandboxBootstrap,
    InMemoryMcpRepository,
    InMemorySandboxAgentRepository,
    InMemorySandboxRepository,
    InMemorySandboxSkillRepository,
)


async def _make(repo: InMemorySandboxRepository, name: str = "alpha") -> Sandbox:
    return await CreateSandbox(repo).execute(
        name=name,
        runtime=SandboxRuntime.COMPOSE,
        image="cappycloud/sandbox:latest",
        env_vars={"FOO": "bar"},
    )


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


def _boot_uc(
    repo: InMemorySandboxRepository,
    runtimes: dict[SandboxRuntime, SandboxRuntimeGateway],
    bootstraps: dict[SandboxRuntime, FakeSandboxBootstrap],
    mcps: InMemoryMcpRepository,
    skills: InMemorySandboxSkillRepository | None = None,
    agents: InMemorySandboxAgentRepository | None = None,
) -> BootSandbox:
    return BootSandbox(
        repo,
        runtimes,
        bootstraps,
        mcps,
        skills or InMemorySandboxSkillRepository(),
        agents or InMemorySandboxAgentRepository(),
    )


class TestBootSandbox:
    async def test_boot_transitions_to_configured_and_writes_settings(
        self,
        repo: InMemorySandboxRepository,
        runtime: FakeRuntimeGateway,
        bootstrap: FakeSandboxBootstrap,
        mcps: InMemoryMcpRepository,
    ) -> None:
        a = await _make(repo, name="alpha")
        runtimes = {SandboxRuntime.COMPOSE: runtime}
        bootstraps = {SandboxRuntime.COMPOSE: bootstrap}

        result = await _boot_uc(repo, runtimes, bootstraps, mcps).execute(a.id)

        assert result.container_status is ContainerStatus.CONFIGURED
        assert runtime.calls == ["ensure"]
        # Bootstrap escreveu o settings.json para esta sandbox:
        assert len(bootstrap.calls) == 1
        called_sandbox_id, called_settings = bootstrap.calls[0]
        assert called_sandbox_id == a.id
        # Sem MCPs cadastrados → mcpServers vazio:
        assert called_settings == {"mcpServers": {}}
        # Sem skills/agents cadastrados → bootstrap chamado com lista vazia:
        assert len(bootstrap.skill_calls) == 1 and bootstrap.skill_calls[0][1] == []
        assert len(bootstrap.agent_calls) == 1 and bootstrap.agent_calls[0][1] == []

    async def test_boot_writes_mcp_servers_from_db(
        self,
        repo: InMemorySandboxRepository,
        runtime: FakeRuntimeGateway,
        bootstrap: FakeSandboxBootstrap,
        mcps: InMemoryMcpRepository,
    ) -> None:
        from app.application.use_cases.mcp_servers import CreateSandboxMcp

        a = await _make(repo, name="alpha")
        await CreateSandboxMcp(mcps).execute(
            sandbox_id=a.id,
            name="github",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-github"],
            env={"GITHUB_TOKEN": "ghp_secret"},
            enabled=True,
        )

        result = await _boot_uc(
            repo,
            {SandboxRuntime.COMPOSE: runtime},
            {SandboxRuntime.COMPOSE: bootstrap},
            mcps,
        ).execute(a.id)

        assert result.container_status is ContainerStatus.CONFIGURED
        _, settings = bootstrap.calls[0]
        # Formato espelha o JSON do openclaude (ADR-004 §6):
        assert settings["mcpServers"]["github"] == {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {"GITHUB_TOKEN": "ghp_secret"},
        }

    async def test_boot_omits_disabled_mcps_from_settings(
        self,
        repo: InMemorySandboxRepository,
        runtime: FakeRuntimeGateway,
        bootstrap: FakeSandboxBootstrap,
        mcps: InMemoryMcpRepository,
    ) -> None:
        from app.application.use_cases.mcp_servers import CreateSandboxMcp

        a = await _make(repo, name="alpha")
        await CreateSandboxMcp(mcps).execute(
            sandbox_id=a.id,
            name="off",
            command="echo",
            args=[],
            env={},
            enabled=False,
        )

        await _boot_uc(
            repo,
            {SandboxRuntime.COMPOSE: runtime},
            {SandboxRuntime.COMPOSE: bootstrap},
            mcps,
        ).execute(a.id)

        _, settings = bootstrap.calls[0]
        assert settings == {"mcpServers": {}}

    async def test_boot_propagates_runtime_failure_and_marks_error(
        self,
        repo: InMemorySandboxRepository,
        bootstrap: FakeSandboxBootstrap,
        mcps: InMemoryMcpRepository,
    ) -> None:
        a = await _make(repo, name="alpha")
        runtime = FakeRuntimeGateway(fail_on="ensure")
        runtimes = {SandboxRuntime.COMPOSE: runtime}
        bootstraps = {SandboxRuntime.COMPOSE: bootstrap}

        with pytest.raises(RuntimeFailureError):
            await _boot_uc(repo, runtimes, bootstraps, mcps).execute(a.id)

        # DB reflete o erro:
        stored = await repo.get(a.id)
        assert stored is not None
        assert stored.container_status is ContainerStatus.ERROR
        # Bootstrap não foi chamado:
        assert bootstrap.calls == []

    async def test_boot_marks_error_when_bootstrap_fails(
        self,
        repo: InMemorySandboxRepository,
        runtime: FakeRuntimeGateway,
        mcps: InMemoryMcpRepository,
    ) -> None:
        from app.ports.sandbox_bootstrap import BootstrapFailureError, SandboxBootstrapGateway

        class FailingBootstrap(SandboxBootstrapGateway):
            async def write_settings_json(self, sandbox, settings):  # type: ignore[no-untyped-def]
                raise BootstrapFailureError("disk full")

            async def write_skills(self, sandbox, skills):  # type: ignore[no-untyped-def]
                pass

            async def write_agents(self, sandbox, agents):  # type: ignore[no-untyped-def]
                pass

        a = await _make(repo, name="alpha")
        with pytest.raises(BootstrapFailureError):
            await _boot_uc(
                repo,
                {SandboxRuntime.COMPOSE: runtime},
                {SandboxRuntime.COMPOSE: FailingBootstrap()},
                mcps,
            ).execute(a.id)

        stored = await repo.get(a.id)
        assert stored is not None
        assert stored.container_status is ContainerStatus.ERROR

    async def test_boot_unknown_runtime_raises(
        self,
        repo: InMemorySandboxRepository,
        bootstrap: FakeSandboxBootstrap,
        mcps: InMemoryMcpRepository,
    ) -> None:
        a = await _make(repo, name="alpha")
        runtimes: dict = {}  # nenhum runtime configurado
        with pytest.raises(RuntimeFailureError, match="não está configurado"):
            await _boot_uc(repo, runtimes, {SandboxRuntime.COMPOSE: bootstrap}, mcps).execute(a.id)

    async def test_boot_unknown_bootstrap_marks_error(
        self,
        repo: InMemorySandboxRepository,
        runtime: FakeRuntimeGateway,
        mcps: InMemoryMcpRepository,
    ) -> None:
        a = await _make(repo, name="alpha")
        with pytest.raises(RuntimeFailureError, match="Bootstrap"):
            await _boot_uc(
                repo,
                {SandboxRuntime.COMPOSE: runtime},
                {},  # nenhum bootstrap configurado
                mcps,
            ).execute(a.id)

        stored = await repo.get(a.id)
        assert stored is not None
        assert stored.container_status is ContainerStatus.ERROR

    async def test_boot_unknown_sandbox(
        self,
        repo: InMemorySandboxRepository,
        runtime: FakeRuntimeGateway,
        bootstrap: FakeSandboxBootstrap,
        mcps: InMemoryMcpRepository,
    ) -> None:
        with pytest.raises(SandboxNotFoundError):
            await _boot_uc(
                repo,
                {SandboxRuntime.COMPOSE: runtime},
                {SandboxRuntime.COMPOSE: bootstrap},
                mcps,
            ).execute(uuid.uuid4())

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

        a = await _make(repo, name="alpha")
        await CreateSandboxSkill(skills).execute(
            sandbox_id=a.id,
            name="naming-conventions",
            description="Convenções de nomenclatura do CappyCloud.",
            content="# Naming\nUse snake_case em Python, camelCase em TS.",
            enabled=True,
        )
        await CreateSandboxAgent(agents).execute(
            sandbox_id=a.id,
            name="reviewer",
            description="Revisor de PRs.",
            system_prompt="Você é um revisor crítico de código.",
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
        ).execute(a.id)

        # Bootstrap recebeu skill + agent na ordem certa:
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
        self, repo: InMemorySandboxRepository, runtime: FakeRuntimeGateway
    ) -> None:
        a = await _make(repo, name="alpha")
        await repo.update_container_status(a.id, ContainerStatus.RUNNING)
        runtimes = {SandboxRuntime.COMPOSE: runtime}

        result = await StopSandbox(repo, runtimes).execute(a.id)

        assert result.container_status is ContainerStatus.STOPPED
        assert runtime.calls == ["stop"]

    async def test_stop_propagates_failure_and_marks_error(
        self, repo: InMemorySandboxRepository
    ) -> None:
        a = await _make(repo, name="alpha")
        runtime = FakeRuntimeGateway(fail_on="stop")
        with pytest.raises(RuntimeFailureError):
            await StopSandbox(repo, {SandboxRuntime.COMPOSE: runtime}).execute(a.id)
        stored = await repo.get(a.id)
        assert stored is not None
        assert stored.container_status is ContainerStatus.ERROR
