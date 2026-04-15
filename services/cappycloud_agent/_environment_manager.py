"""
Environment Manager: manages global environment containers (one per env_slug)
and per-session git worktrees.

Architecture (one-container-per-slug, global):
  • One Docker container per env_slug  → "environment" (cappy_env_<slug>)
  • Container clones the repo to /repos/<slug>/
  • Each conversation gets its own git worktree at /repos/<slug>/sessions/<id>/
  • ChatRequest.working_directory is set to the worktree path.
  • Multiple users can share the same environment container via separate worktrees.

Repository config (repo_url, branch) is always fetched from the canonical
repo_environments table via SessionStore.get_repo_config() — never passed
by callers or stored redundantly in cappy_env_containers.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

import docker
import docker.errors
import httpx

from ._session_store import EnvironmentRecord, SandboxRecord, SessionStore

log = logging.getLogger(__name__)

_REPO_URL_RE = re.compile(
    r"https?://"
    r"(?:[^@\s/]+@)?"
    r"(?:"
    r"github\.com|"
    r"gitlab\.com|"
    r"dev\.azure\.com"
    r")"
    r"/[^\s\"'>]+"
)


def _normalize_repo_url(url: str) -> str:
    """Remove embedded usernames from URLs so git credential helpers work cleanly."""
    return re.sub(r"(https?://)([^@]+@)", r"\1", url)


class EnvironmentManager:
    """Manages global environment containers (per env_slug) and per-session worktrees."""

    def __init__(
        self,
        session_store: SessionStore,
        sandbox_image: str,
        docker_network: str,
        sandbox_grpc_port: int,
        openrouter_api_key: str,
        openrouter_model: str,
        git_auth_token: str = "",
        code_indexer_url: str = "",
    ) -> None:
        self._store = session_store
        self._image = sandbox_image
        self._network = docker_network
        self._grpc_port = sandbox_grpc_port
        self._api_key = openrouter_api_key
        self._model = openrouter_model
        self._git_auth_token = git_auth_token
        self._code_indexer_url = code_indexer_url.rstrip("/")
        self._client = docker.from_env()

    # ── Public API ───────────────────────────────────────────────

    async def get_env_status(self, env_slug: str) -> dict:
        """Return current environment status for a slug."""
        env = await self._store.get_env(env_slug)
        if not env:
            return {"status": "none", "container_id": None}

        docker_status = await asyncio.to_thread(self._container_status, env.container_id)
        if docker_status == "running":
            status = "running"
        elif docker_status in ("exited", "created", "paused"):
            status = "stopped"
        elif docker_status == "starting":
            status = "starting"
        else:
            status = "none"

        return {"status": status, "container_id": env.container_id}

    async def get_or_create_session(
        self,
        user_id: str,
        chat_id: str,
        env_slug: str,
        base_branch: str = "",
    ) -> SandboxRecord:
        """Return a SandboxRecord for the given session, creating the environment
        container and/or the git worktree as needed.

        repo_url and branch are resolved internally from repo_environments.
        base_branch defaults to the canonical branch from repo_environments when empty.
        """
        env = await self._get_or_create_env(env_slug)

        # Resolve base_branch default from canonical repo config
        if not base_branch:
            config = await self._store.get_repo_config(env_slug)
            base_branch = config[1] if config else "main"

        record = await self._store.get(user_id, chat_id)
        if record:
            if await self._worktree_exists(env.container_id, record.worktree_path):
                await self._store.refresh_ttl(user_id, chat_id)
                return record
            else:
                log.warning(
                    "Worktree %s for %s/%s gone — recreating",
                    record.worktree_path,
                    user_id,
                    chat_id,
                )
                await self._store.delete(user_id, chat_id)

        return await self._create_worktree_session(
            user_id, chat_id, env_slug, env, base_branch=base_branch
        )

    async def destroy_session(self, user_id: str, chat_id: str) -> None:
        """Remove the worktree for a session (prune from git + delete record)."""
        record = await self._store.get(user_id, chat_id)
        if not record:
            return

        env = await self._store.get_env(record.env_slug)
        main_repo = f"/repos/{record.env_slug}"
        if env and self._container_running(env.container_id) and record.worktree_path:
            try:
                container = self._client.containers.get(env.container_id)
                container.exec_run(["bash", "-c", f"rm -rf {record.worktree_path}"])
                container.exec_run(["git", "-C", main_repo, "worktree", "prune"])
                log.info(
                    "Removed worktree %s for %s/%s",
                    record.worktree_path,
                    user_id,
                    chat_id,
                )
            except docker.errors.NotFound:
                log.debug("Container for %s already gone", record.env_slug)
            except Exception as exc:
                log.error("Error removing worktree: %s", exc)

        await self._store.delete(user_id, chat_id)

    async def stop_env(self, env_slug: str) -> None:
        """Stop (but do not remove) the persistent environment container for a slug."""
        env = await self._store.get_env(env_slug)
        if not env:
            return

        try:
            container = self._client.containers.get(env.container_id)
            if container.status == "running":
                container.stop(timeout=10)
                log.info("Stopped environment container %s (%s)", env.container_id[:12], env_slug)
        except docker.errors.NotFound:
            log.debug("Environment container for %s already gone", env_slug)
        except Exception as exc:
            log.error("Error stopping environment for %s: %s", env_slug, exc)
        finally:
            await self._store.update_env_status(env_slug, "stopped")

    async def gc_idle_envs(self, env_idle_ttl: int) -> None:
        """Stop environment containers idle longer than env_idle_ttl seconds."""
        idle = await self._store.list_idle_environments(env_idle_ttl)
        for row in idle:
            log.info(
                "GC: stopping idle environment %s (container %s)",
                row["env_slug"],
                row["container_id"][:12],
            )
            await self.stop_env(row["env_slug"])

    async def destroy_env(self, env_slug: str) -> None:
        """Stop and remove the persistent environment container for a slug."""
        env = await self._store.get_env(env_slug)
        if not env:
            return

        try:
            container = self._client.containers.get(env.container_id)
            container.stop(timeout=5)
            container.remove(force=True)
            log.info("Destroyed environment container %s (%s)", env.container_id[:12], env_slug)
        except docker.errors.NotFound:
            log.debug("Environment container for %s already gone", env_slug)
        except Exception as exc:
            log.error("Error destroying environment: %s", exc)
        finally:
            await self._store.delete_env(env_slug)

    async def gc_expired(self) -> None:
        """Destroy worktrees whose idle TTL has expired."""
        expired = await self._store.list_expired_sessions()
        for row in expired:
            await self.destroy_session(row["user_id"], row["chat_id"])

    # ── Environment container management ─────────────────────────

    async def _get_or_create_env(self, env_slug: str) -> EnvironmentRecord:
        """Return a running environment container for the slug, creating one if needed."""
        env = await self._store.get_env(env_slug)

        if env:
            status = self._container_status(env.container_id)
            if status == "running":
                # Verifica se o IP no Redis ainda é válido (pode ter mudado após restart manual)
                try:
                    container = self._client.containers.get(env.container_id)
                    container.reload()
                    networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
                    current_ip = networks.get(self._network, {}).get("IPAddress", "")
                    if current_ip and current_ip != env.container_ip:
                        log.warning(
                            "Container %s (%s) IP changed %s → %s — updating store",
                            env.container_id[:12],
                            env_slug,
                            env.container_ip,
                            current_ip,
                        )
                        await self._store.update_env_ip(env_slug, current_ip)
                        env = EnvironmentRecord(
                            env_slug=env.env_slug,
                            container_id=env.container_id,
                            container_ip=current_ip,
                            status="running",
                        )
                except Exception:
                    pass
                return env
            elif status in ("exited", "created", "paused"):
                log.info(
                    "Environment container %s (%s) is %s — restarting",
                    env.container_id[:12],
                    env_slug,
                    status,
                )
                return await self._restart_env_container(env_slug, env)
            else:
                log.warning(
                    "Environment container %s (%s) gone (status=%r) — recreating",
                    env.container_id[:12],
                    env_slug,
                    status,
                )
                await self._store.delete_env(env_slug)

        return await self._create_env_container(env_slug)

    async def _restart_env_container(
        self, env_slug: str, env: EnvironmentRecord
    ) -> EnvironmentRecord:
        """Start a stopped container, refresh its IP, update the store and wait for gRPC."""
        await self._store.update_env_status(env_slug, "starting")
        try:
            container = self._client.containers.get(env.container_id)
            container.start()
            log.info("Started stopped container %s (%s)", env.container_id[:12], env_slug)
        except docker.errors.NotFound:
            log.warning(
                "Container %s missing on restart — recreating %s",
                env.container_id[:12],
                env_slug,
            )
            await self._store.delete_env(env_slug)
            return await self._create_env_container(env_slug)

        container_ip = ""
        for attempt in range(10):
            container.reload()
            networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
            container_ip = networks.get(self._network, {}).get("IPAddress", "")
            if container_ip:
                break
            log.debug("Waiting for IP after restart (attempt %d/10)…", attempt + 1)
            import time
            time.sleep(1)

        if not container_ip:
            container.remove(force=True)
            await self._store.delete_env(env_slug)
            raise RuntimeError(
                f"Container {env.container_id[:12]} has no IP after restart on network {self._network!r}."
            )

        await self._store.update_env_ip(env_slug, container_ip)
        await self._store.update_env_status(env_slug, "running")

        updated_env = EnvironmentRecord(
            env_slug=env_slug,
            container_id=env.container_id,
            container_ip=container_ip,
            status="running",
        )

        await self._wait_for_grpc(container_ip, self._grpc_port)
        asyncio.create_task(self._trigger_indexing(env_slug))
        return updated_env

    async def _create_env_container(self, env_slug: str) -> EnvironmentRecord:
        """Create a persistent environment container for a slug.

        repo_url and branch are fetched from the canonical repo_environments table.
        """
        repo_url = ""
        branch = "main"
        config = await self._store.get_repo_config(env_slug)
        if config:
            repo_url, branch = config
        else:
            log.warning(
                "env_slug=%r not found in repo_environments — "
                "creating container with no repo (empty workspace)",
                env_slug,
            )

        container_name = f"cappy_env_{env_slug}"
        clean_url = _normalize_repo_url(repo_url) if repo_url else ""

        log.info(
            "Creating environment container %r  slug=%s  repo=%r  branch=%s",
            container_name,
            env_slug,
            clean_url or "(empty)",
            branch,
        )

        if not (self._api_key or "").strip():
            raise RuntimeError(
                "OPENROUTER_API_KEY não está definida ou está vazia. "
                "Define-a no `.env` e reinicia o container da API."
            )

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
                "ENV_SLUG": env_slug,
                "WORKSPACE_REPO": clean_url,
                "WORKSPACE_BRANCH": branch,
                "GRPC_HOST": "0.0.0.0",
                "GRPC_PORT": str(self._grpc_port),
                "GIT_AUTH_TOKEN": self._git_auth_token,
                "CODE_INDEXER_URL": self._code_indexer_url,
                "CAPPY_USER_ID": env_slug,
            },
            network=self._network,
            labels={
                "cappycloud.env_slug": env_slug,
                "cappycloud.managed": "true",
                "cappycloud.type": "environment",
            },
            restart_policy={"Name": "on-failure", "MaximumRetryCount": 3},
            remove=False,
        )

        container_ip = ""
        for attempt in range(10):
            container.reload()
            networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
            container_ip = networks.get(self._network, {}).get("IPAddress", "")
            if container_ip:
                break
            log.debug("Waiting for IP on %s (attempt %d/10)…", self._network, attempt + 1)
            import time
            time.sleep(1)

        if not container_ip:
            all_nets = list(networks.keys())
            container.remove(force=True)
            raise RuntimeError(
                f"Container {container.id[:12]} has no IP on network {self._network!r} "
                f"after 10 retries. Networks visible: {all_nets}. "
                "Check that the Docker network exists: "
                f"docker network inspect {self._network}"
            )

        env_record = EnvironmentRecord(
            env_slug=env_slug,
            container_id=container.id,
            container_ip=container_ip,
            status="running",
        )
        await self._store.save_env(env_record)

        await self._wait_for_grpc(container_ip, self._grpc_port)
        asyncio.create_task(self._trigger_indexing(env_slug))

        return env_record

    # ── Worktree session management ───────────────────────────────

    async def _create_worktree_session(
        self,
        user_id: str,
        chat_id: str,
        env_slug: str,
        env: EnvironmentRecord,
        base_branch: str = "main",
    ) -> SandboxRecord:
        """Create a git worktree for a new conversation and return its SandboxRecord."""
        session_id = chat_id.replace("-", "")[:16]
        worktree_path = f"/repos/{env_slug}/sessions/{session_id}"

        log.info(
            "Creating worktree session %r for %s/%s (env=%s, base_branch=%s)",
            worktree_path,
            user_id,
            chat_id,
            env_slug,
            base_branch,
        )

        try:
            container = self._client.containers.get(env.container_id)
            exit_code, output = container.exec_run(
                ["/session_start.sh", env_slug, session_id, worktree_path, base_branch],
            )
            output_str = output.decode("utf-8", errors="replace") if output else ""
            if exit_code != 0:
                raise RuntimeError(
                    f"session_start.sh failed (exit {exit_code}): {output_str}"
                )
            log.debug("session_start.sh output: %s", output_str.strip())
        except docker.errors.NotFound:
            raise RuntimeError(
                f"Environment container for env_slug={env_slug!r} not found. "
                "It may have been removed unexpectedly."
            )

        record = SandboxRecord(
            user_id=user_id,
            chat_id=chat_id,
            env_slug=env_slug,
            container_id=env.container_id,
            container_ip=env.container_ip,
            grpc_port=self._grpc_port,
            worktree_path=worktree_path,
        )
        await self._store.save(record)
        return record

    # ── Helpers ───────────────────────────────────────────────────

    async def _trigger_indexing(self, env_slug: str) -> None:
        """Dispara indexação headless via code-indexer (fire-and-forget)."""
        if not self._code_indexer_url:
            return
        env = await self._store.get_env(env_slug)
        if not env or not env.container_id:
            log.debug("Indexação ignorada — sem container para env_slug=%s", env_slug)
            return
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"{self._code_indexer_url}/index",
                    json={
                        "user_id": env_slug,
                        "container_id": env.container_id,
                        "workspace_path": f"/repos/{env_slug}",
                    },
                )
            log.info(
                "Indexação headless disparada para env_slug=%s  container=%s",
                env_slug,
                env.container_id[:12],
            )
        except Exception as exc:
            log.warning("Falha ao disparar indexação para %s: %s", env_slug, exc)

    def _container_running(self, container_id: str) -> bool:
        try:
            c = self._client.containers.get(container_id)
            return c.status == "running"
        except docker.errors.NotFound:
            return False

    def _container_status(self, container_id: str) -> str:
        """Return 'running', 'exited', or 'missing' for a container."""
        try:
            c = self._client.containers.get(container_id)
            return c.status
        except docker.errors.NotFound:
            return "missing"

    async def _worktree_exists(self, container_id: str, worktree_path: str) -> bool:
        """Check whether a worktree directory exists inside the container."""
        if not worktree_path:
            return False
        try:
            container = self._client.containers.get(container_id)
            exit_code, _ = container.exec_run(
                ["test", "-e", f"{worktree_path}/.git"],
            )
            return exit_code == 0
        except docker.errors.NotFound:
            return False
        except Exception as exc:
            log.debug("_worktree_exists check failed: %s", exc)
            return False

    async def _wait_for_grpc(
        self,
        host: str,
        port: int,
        timeout: int = 90,
        interval: float = 2.0,
    ) -> None:
        """Poll until the environment's gRPC port is reachable."""
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
            "check environment container logs."
        )
