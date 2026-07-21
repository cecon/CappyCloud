"""Adapter test: fallback HTTP do DockerSandboxBootstrap."""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock

import pytest
from app.adapters.secondary.sandbox_runtime.docker_bootstrap import DockerSandboxBootstrap
from app.domain.entities import Sandbox, SandboxAgent, SandboxRuntime, SandboxSkill
from docker.errors import DockerException


def _sandbox() -> Sandbox:
    return Sandbox(
        id=uuid.uuid4(),
        name="cappycloud-sandbox",
        host="cappycloud-sandbox",
        runtime=SandboxRuntime.COMPOSE,
        image="",
    )


async def test_write_settings_uses_http_when_docker_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        status = 200

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout: int):  # type: ignore[no-untyped-def]
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return Response()

    docker_client = MagicMock()
    docker_client.containers.get.side_effect = DockerException("no docker socket")
    monkeypatch.setattr(
        "app.adapters.secondary.sandbox_runtime.docker_bootstrap.urllib.request.urlopen",
        fake_urlopen,
    )

    adapter = DockerSandboxBootstrap(client=docker_client)
    await adapter.write_settings_json(_sandbox(), {"mcpServers": {"github": {"command": "npx"}}})

    assert captured == {
        "url": "http://cappycloud-sandbox:8080/mcp/configure",
        "timeout": 10,
        "payload": {"mcpServers": {"github": {"command": "npx"}}},
    }


async def test_write_skills_uses_http_when_docker_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _capture_http(monkeypatch)
    docker_client = MagicMock()
    docker_client.containers.get.side_effect = DockerException("no docker socket")

    adapter = DockerSandboxBootstrap(client=docker_client)
    await adapter.write_skills(
        _sandbox(),
        [
            SandboxSkill(
                id=uuid.uuid4(),
                sandbox_id=uuid.uuid4(),
                name="naming",
                description="Convenções",
                content="- Use nomes claros",
                enabled=True,
            )
        ],
    )

    assert captured["url"] == "http://cappycloud-sandbox:8080/globals/configure"
    assert captured["payload"]["skills"][0]["name"] == "naming"
    assert "# naming" in captured["payload"]["skills"][0]["markdown"]


async def test_write_agents_uses_http_when_docker_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _capture_http(monkeypatch)
    docker_client = MagicMock()
    docker_client.containers.get.side_effect = DockerException("no docker socket")

    adapter = DockerSandboxBootstrap(client=docker_client)
    await adapter.write_agents(
        _sandbox(),
        [
            SandboxAgent(
                id=uuid.uuid4(),
                sandbox_id=uuid.uuid4(),
                name="reviewer",
                description="Revisor",
                system_prompt="Revise com cuidado.",
                model="claude-sonnet-4-6",
                tools=["Read"],
                enabled=True,
            )
        ],
    )

    assert captured["url"] == "http://cappycloud-sandbox:8080/globals/configure"
    assert captured["payload"]["agents"][0]["name"] == "reviewer"
    assert "Revise com cuidado." in captured["payload"]["agents"][0]["markdown"]


def _capture_http(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    class Response:
        status = 200

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout: int):  # type: ignore[no-untyped-def]
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return Response()

    monkeypatch.setattr(
        "app.adapters.secondary.sandbox_runtime.docker_bootstrap.urllib.request.urlopen",
        fake_urlopen,
    )
    return captured
