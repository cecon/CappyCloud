"""Adapter Docker para escrever periféricos dentro do container da sandbox.

Implementa :class:`SandboxBootstrapGateway` usando o Docker SDK. Materializa
``~/.claude/settings.json`` via :meth:`Container.put_archive` (escrita atômica
em arquivos do container, sem precisar de ``exec``).

Idempotente: re-escrever o mesmo conteúdo é no-op observável.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import tarfile
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

import docker
from docker.errors import APIError, DockerException, NotFound
from docker.models.containers import Container

from app.adapters.secondary.sandbox_runtime.docker_compose import (
    CONTAINER_PREFIX,
    DockerComposeSandboxRuntime,
)
from app.domain.entities import Sandbox, SandboxAgent, SandboxSkill
from app.ports.sandbox_bootstrap import BootstrapFailureError, SandboxBootstrapGateway

log = logging.getLogger(__name__)

CLAUDE_DIR_IN_CONTAINER = "/root/.claude"
SKILLS_SUBDIR = "skills"
AGENTS_SUBDIR = "agents"


class DockerSandboxBootstrap(SandboxBootstrapGateway):
    """Bootstrap via Docker SDK (Compose, dev). Para Swarm, criar outro adapter."""

    def __init__(self, client: docker.DockerClient | None = None) -> None:
        self._client = client

    def _docker(self) -> docker.DockerClient:
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    async def write_claude_md(self, sandbox: Sandbox) -> None:
        await asyncio.to_thread(self._write_claude_md_sync, sandbox)

    def _write_claude_md_sync(self, sandbox: Sandbox) -> None:
        url = f"http://{sandbox.host}:{sandbox.session_port}/globals/configure"
        self._post_json_http_sync(url, {"claude_md": sandbox.claude_md})
        log.info("Bootstrap escreveu CLAUDE.md via HTTP em %s", url)

    @staticmethod
    def _container_name(sandbox: Sandbox) -> str:
        return f"{CONTAINER_PREFIX}{sandbox.name}"

    async def write_settings_json(self, sandbox: Sandbox, settings: dict) -> None:
        await asyncio.to_thread(self._write_settings_sync, sandbox, settings)

    def _write_settings_sync(self, sandbox: Sandbox, settings: dict) -> None:
        try:
            container = self._require_container(sandbox)
        except BootstrapFailureError as exc:
            try:
                self._write_settings_http_sync(sandbox, settings)
            except BootstrapFailureError as http_exc:
                raise BootstrapFailureError(
                    f"{exc}; fallback HTTP também falhou: {http_exc}"
                ) from http_exc
            return

        # Monta um tar em memória com o arquivo settings.json. Docker
        # put_archive desempacota em ``path`` dentro do container.
        payload = json.dumps(settings, indent=2, sort_keys=True).encode("utf-8")
        tar_bytes = io.BytesIO()
        with tarfile.open(fileobj=tar_bytes, mode="w") as tar:
            info = tarfile.TarInfo(name="settings.json")
            info.size = len(payload)
            info.mtime = int(datetime.now(UTC).timestamp())
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(payload))
        tar_bytes.seek(0)

        # Garantia mínima: pasta tem que existir antes de put_archive.
        # Usamos exec_run (idempotente — mkdir -p) para criar /root/.claude.
        try:
            exit_code, _ = container.exec_run(
                cmd=["mkdir", "-p", CLAUDE_DIR_IN_CONTAINER],
                user="root",
            )
            if exit_code != 0:
                raise BootstrapFailureError(
                    f"mkdir -p {CLAUDE_DIR_IN_CONTAINER} falhou (exit {exit_code})"
                )
            ok = container.put_archive(path=CLAUDE_DIR_IN_CONTAINER, data=tar_bytes.getvalue())
        except APIError as exc:
            raise BootstrapFailureError(
                f"Falha ao escrever settings.json no container: {exc}"
            ) from exc

        if not ok:
            raise BootstrapFailureError(
                "Docker put_archive retornou False ao escrever settings.json."
            )

        log.info(
            "Bootstrap escreveu settings.json em %s:%s (%d bytes)",
            self._container_name(sandbox),
            CLAUDE_DIR_IN_CONTAINER,
            len(payload),
        )

    async def write_skills(self, sandbox: Sandbox, skills: list[SandboxSkill]) -> None:
        await asyncio.to_thread(self._write_skills_sync, sandbox, skills)

    def _write_skills_sync(self, sandbox: Sandbox, skills: list[SandboxSkill]) -> None:
        enabled = [s for s in skills if s.enabled]
        try:
            container = self._require_container(sandbox)
        except BootstrapFailureError as exc:
            if not enabled:
                log.info("Bootstrap sem Docker: nenhuma skill habilitada para materializar.")
                return
            self._write_skills_http_sync(sandbox, enabled, exc)
            return
        skills_dir = f"{CLAUDE_DIR_IN_CONTAINER}/{SKILLS_SUBDIR}"
        # Limpa antes — DB é single source of truth.
        self._reset_dir(container, skills_dir)

        if not enabled:
            return  # Diretório vazio (limpo) é o estado correto.

        tar_bytes = io.BytesIO()
        with tarfile.open(fileobj=tar_bytes, mode="w") as tar:
            for skill in enabled:
                body = self._render_skill_md(skill).encode("utf-8")
                path = f"{skill.name}/SKILL.md"
                self._add_tar_entry(tar, path, body)
        tar_bytes.seek(0)

        try:
            ok = container.put_archive(path=skills_dir, data=tar_bytes.getvalue())
        except APIError as exc:
            raise BootstrapFailureError(f"Docker put_archive (skills) falhou: {exc}") from exc
        if not ok:
            raise BootstrapFailureError("Docker put_archive (skills) retornou False.")

        log.info(
            "Bootstrap escreveu %d skill(s) em %s:%s",
            len(enabled),
            self._container_name(sandbox),
            skills_dir,
        )

    async def write_agents(self, sandbox: Sandbox, agents: list[SandboxAgent]) -> None:
        await asyncio.to_thread(self._write_agents_sync, sandbox, agents)

    def _write_agents_sync(self, sandbox: Sandbox, agents: list[SandboxAgent]) -> None:
        enabled = [a for a in agents if a.enabled]
        try:
            container = self._require_container(sandbox)
        except BootstrapFailureError as exc:
            if not enabled:
                log.info("Bootstrap sem Docker: nenhum agent habilitado para materializar.")
                return
            self._write_agents_http_sync(sandbox, enabled, exc)
            return
        agents_dir = f"{CLAUDE_DIR_IN_CONTAINER}/{AGENTS_SUBDIR}"
        self._reset_dir(container, agents_dir)

        if not enabled:
            return

        tar_bytes = io.BytesIO()
        with tarfile.open(fileobj=tar_bytes, mode="w") as tar:
            for agent in enabled:
                body = self._render_agent_md(agent).encode("utf-8")
                path = f"{agent.name}.md"
                self._add_tar_entry(tar, path, body)
        tar_bytes.seek(0)

        try:
            ok = container.put_archive(path=agents_dir, data=tar_bytes.getvalue())
        except APIError as exc:
            raise BootstrapFailureError(f"Docker put_archive (agents) falhou: {exc}") from exc
        if not ok:
            raise BootstrapFailureError("Docker put_archive (agents) retornou False.")

        log.info(
            "Bootstrap escreveu %d agent(s) em %s:%s",
            len(enabled),
            self._container_name(sandbox),
            agents_dir,
        )

    # ── helpers internos ────────────────────────────────────────────────

    @staticmethod
    def _post_json_http_sync(url: str, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                if not 200 <= response.status < 300:
                    raise BootstrapFailureError(f"HTTP {response.status} ao chamar {url}")
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            raise BootstrapFailureError(f"não foi possível chamar {url}: {exc}") from exc

    @staticmethod
    def _write_settings_http_sync(sandbox: Sandbox, settings: dict) -> None:
        url = f"http://{sandbox.host}:{sandbox.session_port}/mcp/configure"
        DockerSandboxBootstrap._post_json_http_sync(url, settings)

        log.info("Bootstrap escreveu settings.json via HTTP em %s", url)

    def _write_skills_http_sync(
        self, sandbox: Sandbox, skills: list[SandboxSkill], docker_exc: BootstrapFailureError
    ) -> None:
        url = f"http://{sandbox.host}:{sandbox.session_port}/globals/configure"
        payload = {
            "skills": [
                {"name": skill.name, "markdown": self._render_skill_md(skill)} for skill in skills
            ]
        }
        try:
            self._post_json_http_sync(url, payload)
        except BootstrapFailureError as http_exc:
            raise BootstrapFailureError(
                f"{docker_exc}; fallback HTTP de skills também falhou: {http_exc}"
            ) from http_exc
        log.info("Bootstrap escreveu %d skill(s) via HTTP em %s", len(skills), url)

    def _write_agents_http_sync(
        self, sandbox: Sandbox, agents: list[SandboxAgent], docker_exc: BootstrapFailureError
    ) -> None:
        url = f"http://{sandbox.host}:{sandbox.session_port}/globals/configure"
        payload = {
            "agents": [
                {"name": agent.name, "markdown": self._render_agent_md(agent)} for agent in agents
            ]
        }
        try:
            self._post_json_http_sync(url, payload)
        except BootstrapFailureError as http_exc:
            raise BootstrapFailureError(
                f"{docker_exc}; fallback HTTP de agents também falhou: {http_exc}"
            ) from http_exc
        log.info("Bootstrap escreveu %d agent(s) via HTTP em %s", len(agents), url)

    def _require_container(self, sandbox: Sandbox) -> Container:
        names = DockerComposeSandboxRuntime._container_name_candidates(sandbox)
        for name in names:
            try:
                return self._docker().containers.get(name)
            except NotFound:
                continue
            except APIError as exc:
                raise BootstrapFailureError(f"Falha ao consultar Docker: {exc}") from exc
            except DockerException as exc:
                raise BootstrapFailureError(
                    f"Docker indisponível para consultar containers: {exc}"
                ) from exc
        display = "', '".join(names)
        raise BootstrapFailureError(f"Container '{display}' não existe — boot antes de bootstrap.")

    @staticmethod
    def _reset_dir(container: Container, path: str) -> None:
        """Apaga ``path`` e recria vazio. Single source of truth = DB."""
        try:
            exit_code, _ = container.exec_run(
                cmd=["sh", "-c", f"rm -rf {path} && mkdir -p {path}"],
                user="root",
            )
        except APIError as exc:
            raise BootstrapFailureError(f"exec_run falhou ao resetar {path}: {exc}") from exc
        if exit_code != 0:
            raise BootstrapFailureError(f"reset {path} falhou (exit {exit_code})")

    @staticmethod
    def _add_tar_entry(tar: tarfile.TarFile, path: str, payload: bytes) -> None:
        info = tarfile.TarInfo(name=path)
        info.size = len(payload)
        info.mtime = int(datetime.now(UTC).timestamp())
        info.mode = 0o644
        tar.addfile(info, io.BytesIO(payload))

    @staticmethod
    def _render_skill_md(skill: SandboxSkill) -> str:
        """Skill = markdown puro; descrição como subtítulo opcional."""
        parts = [f"# {skill.name}"]
        if skill.description:
            parts.append("")
            parts.append(skill.description)
        if skill.content:
            parts.append("")
            parts.append(skill.content.rstrip())
        return "\n".join(parts) + "\n"

    @staticmethod
    def _render_agent_md(agent: SandboxAgent) -> str:
        """Agent = arquivo .md com frontmatter YAML + corpo (system_prompt)."""
        lines = ["---", f"name: {agent.name}"]
        if agent.description:
            # Description multi-line vira string literal block.
            if "\n" in agent.description:
                lines.append("description: |")
                for line in agent.description.splitlines():
                    lines.append(f"  {line}")
            else:
                lines.append(f"description: {agent.description}")
        if agent.model:
            lines.append(f"model: {agent.model}")
        if agent.tools:
            tools_csv = ", ".join(agent.tools)
            lines.append(f"tools: [{tools_csv}]")
        lines.append("---")
        lines.append("")
        if agent.system_prompt:
            lines.append(agent.system_prompt.rstrip())
        return "\n".join(lines) + "\n"
