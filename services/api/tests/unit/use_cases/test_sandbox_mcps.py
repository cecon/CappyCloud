"""Unit tests for sandbox MCP use cases (ADR-004 §6)."""

from __future__ import annotations

import uuid

import pytest
from app.application.use_cases.mcp_servers import (
    CreateSandboxMcp,
    DeleteSandboxMcp,
    ExportSandboxMcpConfig,
    ListSandboxMcps,
    McpServerNameTakenError,
    McpServerNotFoundError,
    UpdateSandboxMcp,
)

from tests.conftest import InMemoryMcpRepository


@pytest.fixture
def repo() -> InMemoryMcpRepository:
    return InMemoryMcpRepository()


@pytest.fixture
def sandbox_id() -> uuid.UUID:
    return uuid.uuid4()


class TestCreateSandboxMcp:
    async def test_creates_mcp_with_normalised_name(
        self, repo: InMemoryMcpRepository, sandbox_id: uuid.UUID
    ) -> None:
        mcp = await CreateSandboxMcp(repo).execute(
            sandbox_id=sandbox_id,
            name="  github  ",
            command="npx",
            args=["-y", "@mcp/github"],
            env={"GITHUB_TOKEN": "x"},
        )
        assert mcp.name == "github"
        assert mcp.sandbox_id == sandbox_id
        assert mcp.command == "npx"
        assert mcp.args == ["-y", "@mcp/github"]
        assert mcp.env == {"GITHUB_TOKEN": "x"}
        assert mcp.enabled is True

    async def test_rejects_empty_name(
        self, repo: InMemoryMcpRepository, sandbox_id: uuid.UUID
    ) -> None:
        with pytest.raises(ValueError, match="obrigatório"):
            await CreateSandboxMcp(repo).execute(
                sandbox_id=sandbox_id, name="   ", command="echo", args=[], env={}
            )

    async def test_rejects_duplicate_name_in_same_sandbox(
        self, repo: InMemoryMcpRepository, sandbox_id: uuid.UUID
    ) -> None:
        await CreateSandboxMcp(repo).execute(
            sandbox_id=sandbox_id, name="dup", command="echo", args=[], env={}
        )
        with pytest.raises(McpServerNameTakenError, match="dup"):
            await CreateSandboxMcp(repo).execute(
                sandbox_id=sandbox_id, name="dup", command="echo", args=[], env={}
            )

    async def test_allows_same_name_in_different_sandboxes(
        self, repo: InMemoryMcpRepository
    ) -> None:
        sb_a = uuid.uuid4()
        sb_b = uuid.uuid4()
        await CreateSandboxMcp(repo).execute(
            sandbox_id=sb_a, name="github", command="npx", args=[], env={}
        )
        # Mesmo nome, sandbox diferente — não conflita:
        result = await CreateSandboxMcp(repo).execute(
            sandbox_id=sb_b, name="github", command="npx", args=[], env={}
        )
        assert result.sandbox_id == sb_b


class TestListSandboxMcps:
    async def test_returns_only_mcps_of_sandbox(self, repo: InMemoryMcpRepository) -> None:
        sb_a = uuid.uuid4()
        sb_b = uuid.uuid4()
        await CreateSandboxMcp(repo).execute(
            sandbox_id=sb_a, name="alpha", command="echo", args=[], env={}
        )
        await CreateSandboxMcp(repo).execute(
            sandbox_id=sb_b, name="beta", command="echo", args=[], env={}
        )

        result = await ListSandboxMcps(repo).execute(sb_a)

        assert len(result) == 1
        assert result[0].name == "alpha"


class TestUpdateSandboxMcp:
    async def test_updates_existing(
        self, repo: InMemoryMcpRepository, sandbox_id: uuid.UUID
    ) -> None:
        mcp = await CreateSandboxMcp(repo).execute(
            sandbox_id=sandbox_id, name="x", command="echo", args=[], env={}
        )
        updated = await UpdateSandboxMcp(repo).execute(
            mcp_id=mcp.id,
            sandbox_id=sandbox_id,
            name="x",
            command="npx",
            args=["-y"],
            env={"K": "V"},
            enabled=False,
        )
        assert updated.command == "npx"
        assert updated.args == ["-y"]
        assert updated.env == {"K": "V"}
        assert updated.enabled is False

    async def test_rejects_rename_to_existing(
        self, repo: InMemoryMcpRepository, sandbox_id: uuid.UUID
    ) -> None:
        a = await CreateSandboxMcp(repo).execute(
            sandbox_id=sandbox_id, name="a", command="echo", args=[], env={}
        )
        await CreateSandboxMcp(repo).execute(
            sandbox_id=sandbox_id, name="b", command="echo", args=[], env={}
        )
        with pytest.raises(McpServerNameTakenError):
            await UpdateSandboxMcp(repo).execute(
                mcp_id=a.id,
                sandbox_id=sandbox_id,
                name="b",
                command="echo",
                args=[],
                env={},
                enabled=True,
            )

    async def test_missing_raises(self, repo: InMemoryMcpRepository, sandbox_id: uuid.UUID) -> None:
        with pytest.raises(McpServerNotFoundError):
            await UpdateSandboxMcp(repo).execute(
                mcp_id=uuid.uuid4(),
                sandbox_id=sandbox_id,
                name="x",
                command="echo",
                args=[],
                env={},
                enabled=True,
            )

    async def test_wrong_sandbox_treated_as_missing(self, repo: InMemoryMcpRepository) -> None:
        sb_a = uuid.uuid4()
        sb_b = uuid.uuid4()
        a = await CreateSandboxMcp(repo).execute(
            sandbox_id=sb_a, name="x", command="echo", args=[], env={}
        )
        # Tenta atualizar com sandbox_id errado — comporta-se como "não existe":
        with pytest.raises(McpServerNotFoundError):
            await UpdateSandboxMcp(repo).execute(
                mcp_id=a.id,
                sandbox_id=sb_b,
                name="x",
                command="echo",
                args=[],
                env={},
                enabled=True,
            )


class TestDeleteSandboxMcp:
    async def test_deletes_existing(
        self, repo: InMemoryMcpRepository, sandbox_id: uuid.UUID
    ) -> None:
        mcp = await CreateSandboxMcp(repo).execute(
            sandbox_id=sandbox_id, name="x", command="echo", args=[], env={}
        )
        deleted = await DeleteSandboxMcp(repo).execute(mcp.id, sandbox_id)
        assert deleted is True
        assert await repo.get(mcp.id, sandbox_id) is None

    async def test_returns_false_for_missing(
        self, repo: InMemoryMcpRepository, sandbox_id: uuid.UUID
    ) -> None:
        assert await DeleteSandboxMcp(repo).execute(uuid.uuid4(), sandbox_id) is False

    async def test_isolates_by_sandbox_id(self, repo: InMemoryMcpRepository) -> None:
        sb_a = uuid.uuid4()
        sb_b = uuid.uuid4()
        a = await CreateSandboxMcp(repo).execute(
            sandbox_id=sb_a, name="x", command="echo", args=[], env={}
        )
        # Não consegue apagar usando sandbox_id errado:
        deleted = await DeleteSandboxMcp(repo).execute(a.id, sb_b)
        assert deleted is False
        # Linha continua lá:
        assert await repo.get(a.id, sb_a) is not None


class TestExportSandboxMcpConfig:
    async def test_serializes_to_openclaude_format(
        self, repo: InMemoryMcpRepository, sandbox_id: uuid.UUID
    ) -> None:
        await CreateSandboxMcp(repo).execute(
            sandbox_id=sandbox_id,
            name="github",
            command="npx",
            args=["-y", "@mcp/github"],
            env={"TOKEN": "x"},
        )
        await CreateSandboxMcp(repo).execute(
            sandbox_id=sandbox_id,
            name="off",
            command="echo",
            args=[],
            env={},
            enabled=False,
        )

        result = await ExportSandboxMcpConfig(repo).execute(sandbox_id)

        # Formato espelha o JSON do openclaude (ADR-004 §6):
        assert "mcpServers" in result
        # Disabled é omitido:
        assert "off" not in result["mcpServers"]
        # Mantém a forma esperada pelo openclaude:
        assert result["mcpServers"]["github"] == {
            "command": "npx",
            "args": ["-y", "@mcp/github"],
            "env": {"TOKEN": "x"},
        }

    async def test_omits_empty_args_and_env(
        self, repo: InMemoryMcpRepository, sandbox_id: uuid.UUID
    ) -> None:
        await CreateSandboxMcp(repo).execute(
            sandbox_id=sandbox_id, name="minimal", command="echo", args=[], env={}
        )
        result = await ExportSandboxMcpConfig(repo).execute(sandbox_id)
        # args/env vazios não vão pro JSON (mantém limpo):
        assert result["mcpServers"]["minimal"] == {"command": "echo"}
