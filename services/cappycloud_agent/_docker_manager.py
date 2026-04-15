"""
Docker Manager: creates and destroys sandbox containers.

Each sandbox runs the openclaude gRPC server in an isolated environment.
One container is created per (user_id, chat_id) pair and reused until
the session times out.

Port strategy
─────────────
Each sandbox container gets its own IP address on the cappycloud_net
Docker bridge network.  Because IPs are unique, every container can
listen on the SAME internal gRPC port (default 50051) with zero
collision — just like two web servers can both use port 80 on different
machines.  The API service connects to <container_ip>:<grpc_port>;
no host-port mapping is ever required.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

import docker
import docker.errors

from ._session_store import SandboxRecord, SessionStore

log = logging.getLogger(__name__)

# Matches GitHub, GitLab and Azure DevOps repo URLs.
# Azure DevOps format: https://[user@]dev.azure.com/org/project/_git/repo
_REPO_URL_RE = re.compile(
    r"https?://"
    r"(?:[^@\s/]+@)?"            # optional embedded username (e.g. linxpostos@)
    r"(?:"
    r"github\.com|"
    r"gitlab\.com|"
    r"dev\.azure\.com"
    r")"
    r"/[^\s\"'>]+"               # path after host
)


def _normalize_repo_url(url: str) -> str:
    """
    Remove embedded usernames from URLs so git credential helpers work cleanly.

    Azure DevOps clone URLs sometimes embed the org username:
      https://linxpostos@dev.azure.com/... → https://dev.azure.com/...
    The entrypoint.sh re-injects auth via GIT_AUTH_TOKEN insteadOf rewrite.
    """
    return re.sub(r"(https?://)([^@]+@)", r"\1", url)


def _extract_repo_url(messages: list[dict]) -> str:
    """Scan all message content for a git repo URL, returning a normalized URL."""
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            m = _REPO_URL_RE.search(content)
            if m:
                return _normalize_repo_url(m.group(0))
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    m = _REPO_URL_RE.search(part.get("text", ""))
                    if m:
                        return _normalize_repo_url(m.group(0))
    return ""


class DockerManager:
    def __init__(
        self,
        session_store: SessionStore,
        sandbox_image: str,
        docker_network: str,
        sandbox_grpc_port: int,
        openrouter_api_key: str,
        openrouter_model: str,
        workspace_repo: str = "",
        git_auth_token: str = "",
    ) -> None:
        self._store = session_store
        self._image = sandbox_image
        self._network = docker_network
        self._grpc_port = sandbox_grpc_port
        self._api_key = openrouter_api_key
        self._model = openrouter_model
        # Fixed repo — every sandbox clones this on startup
        self._workspace_repo = _normalize_repo_url(workspace_repo) if workspace_repo else ""
        # PAT for private repos (Azure DevOps / GitHub)
        self._git_auth_token = git_auth_token
        self._client = docker.from_env()

    # ── Public API ───────────────────────────────────────────────

    async def get_or_create(
        self,
        user_id: str,
        chat_id: str,
    ) -> SandboxRecord:
        """Return a live SandboxRecord, creating a new sandbox if needed."""
        record = await self._store.get(user_id, chat_id)

        if record:
            if self._container_running(record.container_id):
                await self._store.refresh_ttl(user_id, chat_id)
                return record
            else:
                log.warning(
                    "Container %s for %s/%s gone — recreating",
                    record.container_id[:12],
                    user_id,
                    chat_id,
                )
                await self._store.delete(user_id, chat_id)

        return await self._create_sandbox(user_id, chat_id)

    async def destroy(self, user_id: str, chat_id: str) -> None:
        """Stop and remove the sandbox container for a session."""
        record = await self._store.get(user_id, chat_id)
        if not record:
            return

        try:
            container = self._client.containers.get(record.container_id)
            container.stop(timeout=5)
            container.remove(force=True)
            log.info(
                "Destroyed sandbox %s for %s/%s",
                record.container_id[:12],
                user_id,
                chat_id,
            )
        except docker.errors.NotFound:
            log.debug("Sandbox container %s already gone", record.container_id[:12])
        except Exception as exc:
            log.error("Error destroying sandbox: %s", exc)
        finally:
            await self._store.delete(user_id, chat_id)

    async def gc_expired(self) -> None:
        """Destroy containers whose idle TTL has expired."""
        expired = await self._store.list_expired_containers()
        for row in expired:
            await self.destroy(row["user_id"], row["chat_id"])

    # ── Internals ────────────────────────────────────────────────

    def _container_running(self, container_id: str) -> bool:
        try:
            c = self._client.containers.get(container_id)
            return c.status == "running"
        except docker.errors.NotFound:
            return False

    async def _create_sandbox(self, user_id: str, chat_id: str) -> SandboxRecord:
        workspace_repo = self._workspace_repo

        # Container name: cappy_<user_id[:8]>_<chat_id[:8]>
        # Truncated IDs keep it short but identifiable per user/session.
        container_name = f"cappy_{user_id[:8]}_{chat_id[:8]}"

        log.info(
            "Creating sandbox %r for %s/%s  repo=%r  grpc_port=%d",
            container_name,
            user_id,
            chat_id,
            workspace_repo or "(empty)",
            self._grpc_port,
        )

        if not (self._api_key or "").strip():
            raise RuntimeError(
                "OPENROUTER_API_KEY não está definida ou está vazia no serviço `api`. "
                "Define-a no `.env` (Compose) e reinicia o container."
            )

        # Remove stale container with the same name if it exists
        try:
            old = self._client.containers.get(container_name)
            old.remove(force=True)
            log.debug("Removed stale container %r", container_name)
        except docker.errors.NotFound:
            pass

        container = self._client.containers.run(
            self._image,
            name=container_name,
            detach=True,
            environment={
                "CLAUDE_CODE_USE_OPENAI": "1",
                "OPENAI_BASE_URL": "https://openrouter.ai/api/v1",
                "OPENAI_API_KEY": self._api_key,
                "OPENAI_MODEL": self._model,
                "WORKSPACE_REPO": workspace_repo,
                "GRPC_HOST": "0.0.0.0",
                "GRPC_PORT": str(self._grpc_port),
                # PAT for private repos (Azure DevOps / GitHub)
                "GIT_AUTH_TOKEN": self._git_auth_token,
            },
            # No host-port mapping: the API reaches the
            # container via its Docker-network IP address only.
            network=self._network,
            labels={
                "cappycloud.user_id": user_id,
                "cappycloud.chat_id": chat_id,
                "cappycloud.managed": "true",
            },
            remove=False,
        )

        # Retrieve the IP address — retry because Docker may not have
        # finished the network setup immediately after container start.
        container_ip = ""
        for attempt in range(10):
            container.reload()
            networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
            container_ip = networks.get(self._network, {}).get("IPAddress", "")
            if container_ip:
                break
            log.debug(
                "Waiting for IP on %s (attempt %d/10)…", self._network, attempt + 1
            )
            import time; time.sleep(1)

        if not container_ip:
            # Log full network info for diagnosis
            all_nets = list(networks.keys())
            container.remove(force=True)
            raise RuntimeError(
                f"Container {container.id[:12]} has no IP on network {self._network!r} "
                f"after 10 retries. Networks visible: {all_nets}. "
                "Check that the Docker network exists: "
                f"docker network inspect {self._network}"
            )

        record = SandboxRecord(
            user_id=user_id,
            chat_id=chat_id,
            container_id=container.id,
            container_ip=container_ip,
            grpc_port=self._grpc_port,
            workspace_repo=workspace_repo,
        )
        await self._store.save(record)

        # Wait until the gRPC server inside the container is accepting connections
        await self._wait_for_grpc(container_ip, self._grpc_port)

        return record

    async def _wait_for_grpc(
        self,
        host: str,
        port: int,
        timeout: int = 90,
        interval: float = 2.0,
    ) -> None:
        """Poll until the sandbox's gRPC port is reachable via the Docker network."""
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            try:
                reader, writer = await asyncio.open_connection(host, port)
                writer.close()
                await writer.wait_closed()
                log.info("gRPC ready at %s:%d", host, port)
                return
            except (ConnectionRefusedError, OSError):
                await asyncio.sleep(interval)

        raise TimeoutError(
            f"gRPC server at {host}:{port} not ready after {timeout}s — "
            "check sandbox container logs: "
            f"docker logs $(docker ps -q --filter label=cappycloud.user_id={host})"
        )
