"""
CappyCloud Agent Pipeline — Option C: Interactive choices

Key behaviours:
  - Each (user_id, chat_id) maps to one sandbox container + one GrpcSession
  - GrpcSession is persistent: the gRPC stream stays open between pipe() calls
  - When openclaude emits ActionRequired, the stream PAUSES and the user sees
    a formatted choice prompt in the chat
  - The user's next message is detected as a reply and routed back to the stream
  - New conversation turns (no pending action) send a new ChatRequest on the
    same session_id so openclaude maintains context

Routing logic in pipe():
  ┌───────────────────────────────────┐
  │  Pending action for this session? │
  ├───── YES ─────────────────────────┤
  │  → send_input(user_message)       │
  │  → drain remainder of stream      │
  ├───── NO + live session ───────────┤
  │  → send_message(user_message)     │
  │  → drain                          │
  ├───── NO + no session ─────────────┤
  │  → create sandbox                 │
  │  → GrpcSession.start(message)     │
  │  → drain                          │
  └───────────────────────────────────┘
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import sys
from collections.abc import Generator
from queue import Empty, Queue
from typing import Optional

from pydantic import BaseModel, Field

for _p in ("/app", "/app/pipelines"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _docker_manager import DockerManager  # noqa: E402
from _grpc_session import GrpcSession, PendingAction, _DONE  # noqa: E402
from _session_store import SessionStore  # noqa: E402

log = logging.getLogger(__name__)


def _stable_chat_id(messages: list[dict]) -> str:
    """SHA-1 of the first user message → stable chat identifier."""
    first = next(
        (m.get("content", "") for m in messages if m.get("role") == "user"),
        "",
    )
    if isinstance(first, list):
        first = " ".join(p.get("text", "") for p in first if isinstance(p, dict))
    return hashlib.sha1(first[:300].encode()).hexdigest()[:16]


def _user_id_from_body(body: dict) -> str:
    """
    Resolve o ID do utilizador para o par (user_id, chat_id).

    O Open WebUI envia ``user`` como dict com ``id``. O LibreChat pode enviar
    ``user`` como string (ex.: ObjectId MongoDB) — nesse caso não usar ``.get``.
    """
    raw = body.get("user")
    if raw is None:
        return str(body.get("user_id") or "anonymous")
    if isinstance(raw, dict):
        return str(raw.get("id") or body.get("user_id") or "anonymous")
    return str(raw)


def _format_action(action: PendingAction) -> str:
    """
    Render an ActionRequired event as a clean chat message with visible choices.
    """
    lines = ["\n\n---\n"]

    if action.is_confirmation:
        lines.append("**O agente precisa da sua confirmação:**\n")
        lines.append(f"> {action.question}\n\n")
        lines.append("Responda:\n")
        lines.append("- **`sim`** — prosseguir\n")
        lines.append("- **`não`** — cancelar\n")

    else:
        lines.append("**O agente precisa de mais informações:**\n")
        # Strip bracket-encoded choices from the question text for clean display
        import re

        clean_q = re.sub(r"\s*\[[^\]]+\]", "", action.question).strip()
        lines.append(f"> {clean_q}\n")

        if action.choices:
            lines.append("\nEscolha uma das opções:\n\n")
            for i, choice in enumerate(action.choices, 1):
                lines.append(f"**{i}.** {choice}\n")
            lines.append(
                "\n_Digite o número ou o nome da opção (ex: `1` ou `"
                + action.choices[0]
                + "`)_\n"
            )
        else:
            lines.append("\nDigite sua resposta na caixa abaixo.\n")

    lines.append("\n---\n")
    return "".join(lines)


class Pipeline:
    class Valves(BaseModel):
        OPENROUTER_API_KEY: str = Field(default="")
        OPENROUTER_MODEL: str = Field(default="anthropic/claude-3.5-sonnet")
        WORKSPACE_REPO: str = Field(default="")
        GIT_AUTH_TOKEN: str = Field(default="")
        SANDBOX_IMAGE: str = Field(default="cappycloud-sandbox:latest")
        DOCKER_NETWORK: str = Field(default="cappycloud_net")
        SANDBOX_GRPC_PORT: int = Field(default=50051)
        SANDBOX_IDLE_TIMEOUT: int = Field(default=1800)
        REDIS_URL: str = Field(default="redis://redis:6379")
        DATABASE_URL: str = Field(default="")

    def __init__(self) -> None:
        self.name = "CappyCloud Agent"
        self.valves = self.Valves(
            OPENROUTER_API_KEY=os.getenv("OPENROUTER_API_KEY", ""),
            OPENROUTER_MODEL=os.getenv(
                "OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet"
            ),
            WORKSPACE_REPO=os.getenv("WORKSPACE_REPO", ""),
            GIT_AUTH_TOKEN=os.getenv("GIT_AUTH_TOKEN", ""),
            SANDBOX_IMAGE=os.getenv("SANDBOX_IMAGE", "cappycloud-sandbox:latest"),
            DOCKER_NETWORK=os.getenv("DOCKER_NETWORK", "cappycloud_net"),
            SANDBOX_GRPC_PORT=int(os.getenv("SANDBOX_GRPC_PORT", "50051")),
            SANDBOX_IDLE_TIMEOUT=int(os.getenv("SANDBOX_IDLE_TIMEOUT", "1800")),
            REDIS_URL=os.getenv("REDIS_URL", "redis://redis:6379"),
            DATABASE_URL=os.getenv("DATABASE_URL", ""),
        )

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._store: Optional[SessionStore] = None
        self._docker: Optional[DockerManager] = None
        self._gc_task: Optional[asyncio.Task] = None

        # Active GrpcSession objects keyed by (user_id, chat_id)
        # Lives only in memory — reset on pipeline restart
        self._sessions: dict[tuple[str, str], GrpcSession] = {}

    # ── Lifecycle ────────────────────────────────────────────────

    async def on_startup(self) -> None:
        log.info("CappyCloud pipeline starting up…")
        self._loop = asyncio.get_running_loop()

        self._store = SessionStore(
            redis_url=self.valves.REDIS_URL,
            database_url=self.valves.DATABASE_URL,
            idle_ttl=self.valves.SANDBOX_IDLE_TIMEOUT,
        )
        await self._store.connect()

        self._docker = DockerManager(
            session_store=self._store,
            sandbox_image=self.valves.SANDBOX_IMAGE,
            docker_network=self.valves.DOCKER_NETWORK,
            sandbox_grpc_port=self.valves.SANDBOX_GRPC_PORT,
            openrouter_api_key=self.valves.OPENROUTER_API_KEY,
            openrouter_model=self.valves.OPENROUTER_MODEL,
            workspace_repo=self.valves.WORKSPACE_REPO,
            git_auth_token=self.valves.GIT_AUTH_TOKEN,
        )

        self._gc_task = asyncio.create_task(self._gc_loop())
        log.info(
            "CappyCloud pipeline ready. Repo: %s",
            self.valves.WORKSPACE_REPO or "(não configurado)",
        )

    async def on_shutdown(self) -> None:
        log.info("CappyCloud pipeline shutting down…")
        if self._gc_task:
            self._gc_task.cancel()
        for session in list(self._sessions.values()):
            await session.close()
        self._sessions.clear()
        if self._store:
            await self._store.close()

    # ── Sync helper ──────────────────────────────────────────────

    def _run(self, coro, timeout: float = 120):
        if self._loop is None:
            raise RuntimeError("Pipeline not started")
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(
            timeout=timeout
        )

    # ── Main entry point ─────────────────────────────────────────

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: list,
        body: dict,
    ) -> Generator[str, None, None]:
        user_id = _user_id_from_body(body)
        chat_id = _stable_chat_id(messages)
        session_key = (user_id, chat_id)

        log.info("pipe() user=%s chat=%s msg=%r", user_id, chat_id, user_message[:80])

        # ── Route the message ────────────────────────────────────
        session: Optional[GrpcSession] = self._sessions.get(session_key)

        if session and session.is_alive() and session.pending_action:
            # ── Case 1: User is answering a pending choice ────────
            log.info("Routing reply to pending action: %r", user_message)
            self._run(session.send_input(user_message), timeout=10)

        elif session and session.is_alive():
            # ── Case 2: Continue existing conversation ────────────
            log.info("Continuing live session")
            self._run(session.send_message(user_message), timeout=10)

        else:
            # ── Case 3: New session — acquire sandbox first ───────
            if session:
                # Dead session — clean up
                self._run(session.close(), timeout=5)
                del self._sessions[session_key]

            try:
                sandbox = self._run(
                    self._docker.get_or_create(user_id=user_id, chat_id=chat_id),
                    timeout=180,
                )
            except TimeoutError as exc:
                yield f"**Timeout ao iniciar o agente.** {exc}\n"
                return
            except Exception as exc:
                log.exception("Falha ao criar sandbox")
                yield f"**Erro ao iniciar o agente:** {exc}\n"
                return

            session = GrpcSession(
                container_ip=sandbox.container_ip,
                grpc_port=sandbox.grpc_port,
                session_id=f"{user_id}:{chat_id}",
                model=self.valves.OPENROUTER_MODEL,
            )
            try:
                self._run(session.start(user_message), timeout=30)
            except Exception as exc:
                log.exception("Falha ao iniciar sessão gRPC")
                yield f"**Erro ao conectar ao agente:** {exc}\n"
                return

            self._sessions[session_key] = session

        # ── Drain output from the session ────────────────────────
        out_q: Queue = Queue()

        asyncio.run_coroutine_threadsafe(session.drain_to(out_q), self._loop)

        while True:
            try:
                event_type, data = out_q.get(timeout=300)
            except Empty:
                yield "\n\n**Timeout:** agente sem resposta por 5 minutos.\n"
                break

            if event_type is _DONE:
                # Stream ended naturally (done or error)
                if isinstance(data, str):
                    yield f"\n\n**Erro do agente:** {data}\n"
                # Clean up dead session
                if session_key in self._sessions:
                    del self._sessions[session_key]
                break

            elif event_type == "text":
                yield data

            elif event_type == "action":
                # Stream paused — render choices and wait for user response
                action: PendingAction = data
                yield _format_action(action)
                break  # pipe() returns; next user message resumes the session

            elif event_type == "timeout":
                yield "\n\n**Timeout:** agente demorou muito para responder.\n"
                break

    # ── GC ───────────────────────────────────────────────────────

    async def _gc_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(300)
                # Clean up dead sessions
                dead = [k for k, s in self._sessions.items() if not s.is_alive()]
                for k in dead:
                    await self._sessions.pop(k).close()
                if self._docker:
                    await self._docker.gc_expired()
            except asyncio.CancelledError:
                break
            except Exception:
                log.exception("GC loop error")
