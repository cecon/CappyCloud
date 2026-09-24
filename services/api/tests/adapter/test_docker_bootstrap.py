"""Adapter test: DockerSandboxBootstrap contra mock do Docker SDK (ADR-004 §5)."""

from __future__ import annotations

import io
import tarfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from app.adapters.secondary.sandbox_runtime.docker_bootstrap import (
    AGENTS_SUBDIR,
    CLAUDE_DIR_IN_CONTAINER,
    SKILLS_SUBDIR,
    DockerSandboxBootstrap,
)
from app.domain.entities import Sandbox, SandboxAgent, SandboxRuntime, SandboxSkill
from app.ports.sandbox_bootstrap import BootstrapFailureError

OPENCLAUDE_V028_SHA = "6e30b40de00868a968bdcaa0c3d0dd915d69d357"


def test_sandbox_dockerfile_pins_openclaude_v028_sha() -> None:
    dockerfile = Path(__file__).resolve().parents[4] / "services" / "sandbox" / "Dockerfile"

    content = dockerfile.read_text(encoding="utf-8")

    assert f"ARG OPENCLAUDE_REF={OPENCLAUDE_V028_SHA}" in content


def _sandbox(name: str = "alpha") -> Sandbox:
    return Sandbox(
        id=uuid.uuid4(),
        name=name,
        host=name,
        runtime=SandboxRuntime.COMPOSE,
        image="cappy/sandbox:latest",
    )


@pytest.fixture
def docker_client() -> MagicMock:
    client = MagicMock()
    client.containers = MagicMock()
    return client


@pytest.fixture
def adapter(docker_client: MagicMock) -> DockerSandboxBootstrap:
    return DockerSandboxBootstrap(client=docker_client)


class TestWriteSettingsJson:
    async def test_merges_via_session_server_without_touching_docker(
        self,
        adapter: DockerSandboxBootstrap,
        docker_client: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """settings.json fica no volume do Claude Code: nunca sobrescrever o arquivo."""
        posted: list[tuple[str, dict]] = []
        monkeypatch.setattr(
            DockerSandboxBootstrap,
            "_post_json_http_sync",
            staticmethod(lambda url, payload: posted.append((url, payload))),
        )
        settings = {"mcpServers": {"github": {"command": "npx"}}}

        await adapter.write_settings_json(_sandbox(name="alpha"), settings)

        assert posted == [("http://alpha:8080/mcp/configure", settings)]
        docker_client.containers.get.assert_not_called()

    async def test_raises_when_session_server_fails(
        self, adapter: DockerSandboxBootstrap, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fail(url: str, payload: dict) -> None:
            raise BootstrapFailureError(f"não foi possível chamar {url}")

        monkeypatch.setattr(DockerSandboxBootstrap, "_post_json_http_sync", staticmethod(fail))

        with pytest.raises(BootstrapFailureError, match="mcp/configure"):
            await adapter.write_settings_json(_sandbox(), {})


def _skill(name: str = "naming") -> SandboxSkill:
    return SandboxSkill(
        id=uuid.uuid4(),
        sandbox_id=uuid.uuid4(),
        name=name,
        description="convenções",
        content="# Naming\n- snake_case em Python",
        enabled=True,
    )


def _agent(name: str = "reviewer") -> SandboxAgent:
    return SandboxAgent(
        id=uuid.uuid4(),
        sandbox_id=uuid.uuid4(),
        name=name,
        description="Revisor de PRs",
        system_prompt="Você é crítico de código.",
        model="claude-sonnet-4-6",
        tools=["Read", "Grep"],
        enabled=True,
    )


def _extract_file_from_tar(tar_bytes: bytes, member_path: str) -> str:
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r") as tar:
        member = tar.getmember(member_path)
        extracted = tar.extractfile(member)
        assert extracted is not None
        return extracted.read().decode("utf-8")


class TestWriteSkills:
    async def test_resets_dir_and_writes_skill_md(
        self, adapter: DockerSandboxBootstrap, docker_client: MagicMock
    ) -> None:
        sb = _sandbox(name="alpha")
        container = MagicMock()
        container.exec_run.return_value = (0, b"")
        container.put_archive.return_value = True
        docker_client.containers.get.return_value = container

        skill = _skill(name="naming-conventions")
        await adapter.write_skills(sb, [skill])

        reset_call = container.exec_run.call_args_list[0]
        cmd = reset_call.kwargs["cmd"]
        assert cmd[0] == "sh" and "rm -rf" in cmd[2] and SKILLS_SUBDIR in cmd[2]

        put_call = container.put_archive.call_args
        assert put_call.kwargs["path"] == f"{CLAUDE_DIR_IN_CONTAINER}/{SKILLS_SUBDIR}"
        rendered = _extract_file_from_tar(put_call.kwargs["data"], "naming-conventions/SKILL.md")
        # Frontmatter YAML: sem ele o Claude Code não reconhece a skill.
        assert rendered.startswith("---\nname: naming-conventions\ndescription: ")
        # O conteúdo já tem título: não ganha um "# naming-conventions" extra.
        assert "\n---\n\n# Naming\n" in rendered
        assert "convenções" in rendered
        assert "snake_case" in rendered

    async def test_skips_disabled_skills(
        self, adapter: DockerSandboxBootstrap, docker_client: MagicMock
    ) -> None:
        sb = _sandbox(name="alpha")
        container = MagicMock()
        container.exec_run.return_value = (0, b"")
        docker_client.containers.get.return_value = container

        disabled = _skill(name="off")
        disabled.enabled = False
        await adapter.write_skills(sb, [disabled])

        container.put_archive.assert_not_called()

    async def test_empty_list_just_resets_dir(
        self, adapter: DockerSandboxBootstrap, docker_client: MagicMock
    ) -> None:
        sb = _sandbox(name="alpha")
        container = MagicMock()
        container.exec_run.return_value = (0, b"")
        docker_client.containers.get.return_value = container

        await adapter.write_skills(sb, [])

        container.exec_run.assert_called_once()
        container.put_archive.assert_not_called()


class TestWriteAgents:
    async def test_writes_md_with_frontmatter(
        self, adapter: DockerSandboxBootstrap, docker_client: MagicMock
    ) -> None:
        sb = _sandbox(name="alpha")
        container = MagicMock()
        container.exec_run.return_value = (0, b"")
        container.put_archive.return_value = True
        docker_client.containers.get.return_value = container

        agent = _agent(name="reviewer")
        await adapter.write_agents(sb, [agent])

        put_call = container.put_archive.call_args
        assert put_call.kwargs["path"] == f"{CLAUDE_DIR_IN_CONTAINER}/{AGENTS_SUBDIR}"
        rendered = _extract_file_from_tar(put_call.kwargs["data"], "reviewer.md")
        # Frontmatter YAML padrão:
        assert rendered.startswith("---\n")
        assert "name: reviewer" in rendered
        assert "model: claude-sonnet-4-6" in rendered
        assert "tools: [Read, Grep]" in rendered
        # Body = system_prompt:
        assert "Você é crítico de código." in rendered

    async def test_multiline_description_uses_block_scalar(
        self, adapter: DockerSandboxBootstrap, docker_client: MagicMock
    ) -> None:
        sb = _sandbox(name="alpha")
        container = MagicMock()
        container.exec_run.return_value = (0, b"")
        container.put_archive.return_value = True
        docker_client.containers.get.return_value = container

        agent = _agent(name="multi")
        agent.description = "linha 1\nlinha 2"
        agent.tools = []
        agent.model = ""
        await adapter.write_agents(sb, [agent])

        rendered = _extract_file_from_tar(
            container.put_archive.call_args.kwargs["data"], "multi.md"
        )
        # YAML block scalar para descrição multi-line:
        assert "description: |" in rendered
        assert "  linha 1" in rendered
        assert "  linha 2" in rendered
        # Sem ``model:`` ou ``tools:`` quando vazios — fica enxuto:
        assert "model:" not in rendered
        assert "tools:" not in rendered

    async def test_skips_disabled_agents(
        self, adapter: DockerSandboxBootstrap, docker_client: MagicMock
    ) -> None:
        sb = _sandbox(name="alpha")
        container = MagicMock()
        container.exec_run.return_value = (0, b"")
        docker_client.containers.get.return_value = container

        disabled = _agent(name="off")
        disabled.enabled = False
        await adapter.write_agents(sb, [disabled])

        container.put_archive.assert_not_called()


class TestResetDirFailure:
    async def test_skills_raises_when_reset_fails(
        self, adapter: DockerSandboxBootstrap, docker_client: MagicMock
    ) -> None:
        sb = _sandbox(name="alpha")
        container = MagicMock()
        container.exec_run.return_value = (1, b"permission denied")
        docker_client.containers.get.return_value = container

        with pytest.raises(BootstrapFailureError, match="reset"):
            await adapter.write_skills(sb, [_skill()])
