"""Unit tests for admin_sandboxes use cases (ADR-004)."""

from __future__ import annotations

import uuid

import pytest
from app.application.use_cases.admin_sandboxes import (
    BootSandbox,
    CloneSandbox,
    CreateSandbox,
    DeleteSandbox,
    GetSandbox,
    ListSandboxes,
    SandboxInUseError,
    SandboxNameTakenError,
    SandboxNotFoundError,
    StopSandbox,
    UpdateSandbox,
)
from app.domain.entities import ContainerStatus, Sandbox, SandboxRuntime
from app.ports.sandbox_runtime import (
    RuntimeFailureError,
    RuntimeProbe,
    SandboxRuntimeGateway,
)

from tests.conftest import (
    FakeSandboxBootstrap,
    InMemoryMcpRepository,
    InMemorySandboxAgentRepository,
    InMemorySandboxRepository,
    InMemorySandboxSkillRepository,
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


@pytest.fixture
def repo() -> InMemorySandboxRepository:
    return InMemorySandboxRepository()


@pytest.fixture
def runtime() -> FakeRuntimeGateway:
    return FakeRuntimeGateway()


async def _make(repo: InMemorySandboxRepository, name: str = "alpha") -> Sandbox:
    return await CreateSandbox(repo).execute(
        name=name,
        runtime=SandboxRuntime.COMPOSE,
        image="cappycloud/sandbox:latest",
        env_vars={"FOO": "bar"},
    )


class TestCreateSandbox:
    async def test_creates_with_defaults(self, repo: InMemorySandboxRepository) -> None:
        sb = await _make(repo, name="alpha")
        assert sb.name == "alpha"
        assert sb.runtime is SandboxRuntime.COMPOSE
        assert sb.container_status is ContainerStatus.NOT_CREATED
        assert sb.image == "cappycloud/sandbox:latest"
        assert sb.env_vars == {"FOO": "bar"}
        assert sb.host == "alpha"

    async def test_rejects_duplicate_name(self, repo: InMemorySandboxRepository) -> None:
        await _make(repo, name="alpha")
        with pytest.raises(SandboxNameTakenError, match="alpha"):
            await _make(repo, name="alpha")

    async def test_rejects_empty_name(self, repo: InMemorySandboxRepository) -> None:
        with pytest.raises(ValueError, match="obrigatório"):
            await CreateSandbox(repo).execute(
                name="   ",
                runtime=SandboxRuntime.COMPOSE,
                image="x",
            )


class TestListSandboxes:
    async def test_empty(self, repo: InMemorySandboxRepository) -> None:
        assert await ListSandboxes(repo).execute() == []

    async def test_ordered_by_created_at(self, repo: InMemorySandboxRepository) -> None:
        a = await _make(repo, name="alpha")
        b = await _make(repo, name="beta")
        result = await ListSandboxes(repo).execute()
        assert [s.id for s in result] == [a.id, b.id]


class TestGetSandbox:
    async def test_found(self, repo: InMemorySandboxRepository) -> None:
        a = await _make(repo, name="alpha")
        result = await GetSandbox(repo).execute(a.id)
        assert result.id == a.id

    async def test_missing_raises(self, repo: InMemorySandboxRepository) -> None:
        with pytest.raises(SandboxNotFoundError):
            await GetSandbox(repo).execute(uuid.uuid4())


class TestUpdateSandbox:
    async def test_partial_update_preserves_other_fields(
        self, repo: InMemorySandboxRepository
    ) -> None:
        a = await _make(repo, name="alpha")
        updated = await UpdateSandbox(repo).execute(a.id, image="new/img:v2")
        assert updated.image == "new/img:v2"
        # Outros campos preservados:
        assert updated.env_vars == {"FOO": "bar"}
        assert updated.runtime is SandboxRuntime.COMPOSE
        assert updated.name == "alpha"

    async def test_env_vars_replaced_not_merged(self, repo: InMemorySandboxRepository) -> None:
        a = await _make(repo, name="alpha")
        updated = await UpdateSandbox(repo).execute(a.id, env_vars={"NEW": "x"})
        # Replace, não merge — chave antiga sumiu:
        assert updated.env_vars == {"NEW": "x"}

    async def test_missing_raises(self, repo: InMemorySandboxRepository) -> None:
        with pytest.raises(SandboxNotFoundError):
            await UpdateSandbox(repo).execute(uuid.uuid4(), image="x")


class TestDeleteSandbox:
    async def test_deletes_when_not_created(self, repo: InMemorySandboxRepository) -> None:
        a = await _make(repo, name="alpha")
        await DeleteSandbox(repo).execute(a.id)
        assert await repo.get(a.id) is None

    async def test_deletes_when_stopped(self, repo: InMemorySandboxRepository) -> None:
        a = await _make(repo, name="alpha")
        await repo.update_container_status(a.id, ContainerStatus.STOPPED)
        await DeleteSandbox(repo).execute(a.id)
        assert await repo.get(a.id) is None

    @pytest.mark.parametrize(
        "active_status",
        [
            ContainerStatus.STARTING,
            ContainerStatus.RUNNING,
            ContainerStatus.CONFIGURING,
            ContainerStatus.CONFIGURED,
        ],
    )
    async def test_blocks_when_container_active(
        self,
        repo: InMemorySandboxRepository,
        active_status: ContainerStatus,
    ) -> None:
        a = await _make(repo, name="alpha")
        await repo.update_container_status(a.id, active_status)
        with pytest.raises(SandboxInUseError, match="em uso"):
            await DeleteSandbox(repo).execute(a.id)
        # Sandbox preservada:
        assert await repo.get(a.id) is not None

    async def test_missing_raises(self, repo: InMemorySandboxRepository) -> None:
        with pytest.raises(SandboxNotFoundError):
            await DeleteSandbox(repo).execute(uuid.uuid4())


class TestCloneSandbox:
    async def test_clones_config_resets_runtime_state(
        self, repo: InMemorySandboxRepository
    ) -> None:
        a = await _make(repo, name="alpha")
        await repo.update_container_status(a.id, ContainerStatus.RUNNING)

        clone = await CloneSandbox(repo).execute(a.id, "alpha-copy")

        assert clone.name == "alpha-copy"
        assert clone.id != a.id
        # Config copiada:
        assert clone.image == a.image
        assert clone.env_vars == a.env_vars
        assert clone.runtime is a.runtime
        # Runtime state reset:
        assert clone.container_status is ContainerStatus.NOT_CREATED
        assert clone.host == "alpha-copy"
        # Original preservada:
        original = await repo.get(a.id)
        assert original is not None
        assert original.container_status is ContainerStatus.RUNNING

    async def test_rejects_name_collision(self, repo: InMemorySandboxRepository) -> None:
        a = await _make(repo, name="alpha")
        await _make(repo, name="beta")
        with pytest.raises(SandboxNameTakenError):
            await CloneSandbox(repo).execute(a.id, "beta")

    async def test_source_not_found(self, repo: InMemorySandboxRepository) -> None:
        with pytest.raises(SandboxNotFoundError):
            await CloneSandbox(repo).execute(uuid.uuid4(), "new")


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
        # O conteúdo é o markdown bruto do DB (renderização do .md fica no adapter):
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
