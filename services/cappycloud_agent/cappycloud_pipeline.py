"""
CappyCloud Agent Pipeline — Interactive choices

Key behaviours:
  - Each (user_id, chat_id) maps to one sandbox container + one GrpcSession
  - GrpcSession is persistent: the gRPC stream stays open between pipe() calls
  - When openclaude emits ActionRequired, the stream PAUSES and the user sees
    a formatted choice prompt in the chat
  - The user's next message is detected as a reply and routed back to the stream
  - New conversation turns (no pending action) send a new ChatRequest on the
    same session_id so openclaude maintains context
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from collections.abc import Generator
from queue import Empty, Queue
from typing import Optional

from pydantic import BaseModel, Field

from ._docker_manager import DockerManager
from ._grpc_session import GrpcSession, PendingAction, _DONE
from ._session_store import SessionStore

log = logging.getLogger(__name__)


def _agent_database_url() -> str:
    """URL PostgreSQL para o SessionStore (sem prefixo SQLAlchemy ``+asyncpg``)."""
    explicit = os.getenv("PIPELINE_DATABASE_URL", "").strip()
    if explicit:
        return explicit
    fallback = os.getenv("DATABASE_URL", "")
    return fallback.replace("postgresql+asyncpg://", "postgresql://", 1)


def _stable_chat_id(messages: list[dict]) -> str:
    """SHA-1 of the first user message → fallback chat identifier."""
    first = next(
        (m.get("content", "") for m in messages if m.get("role") == "user"),
        "",
    )
    if isinstance(first, list):
        first = " ".join(p.get("text", "") for p in first if isinstance(p, dict))
    return hashlib.sha1(first[:300].encode()).hexdigest()[:16]


def _chat_id_from_body(body: dict, messages: list) -> str:
    """
    Prefer explicit conversation id from the API (PostgreSQL), else legacy hash.
    """
    explicit = body.get("conversation_id") or body.get("chat_id")
    if explicit:
        return str(explicit)
    return _stable_chat_id(messages)


def _user_id_from_body(body: dict) -> str:
    """
    Resolve user id for the (user_id, chat_id) pair.

    Legacy: Open WebUI sends ``user`` as dict; LibreChat as string ObjectId.
    FastAPI sends ``user_id`` or ``user``: { "id": "..." }.
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
            DATABASE_URL=_agent_database_url(),
        )

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._store: Optional[SessionStore] = None
        self._docker: Optional[DockerManager] = None
        self._gc_task: Optional[asyncio.Task] = None

        self._sessions: dict[tuple[str, str], GrpcSession] = {}

    async def on_startup(self) -> None:
        log.info("CappyCloud agent pipeline starting…")
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
            "CappyCloud agent ready. Repo: %s",
            self.valves.WORKSPACE_REPO or "(não configurado)",
        )

    async def on_shutdown(self) -> None:
        log.info("CappyCloud agent pipeline shutting down…")
        if self._gc_task:
            self._gc_task.cancel()
        for session in list(self._sessions.values()):
            await session.close()
        self._sessions.clear()
        if self._store:
            await self._store.close()

    def _run(self, coro, timeout: float = 120):
        if self._loop is None:
            raise RuntimeError("Pipeline not started")
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout=timeout)

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: list,
        body: dict,
    ) -> Generator[str, None, None]:
        user_id = _user_id_from_body(body)
        chat_id = _chat_id_from_body(body, messages)
        session_key = (user_id, chat_id)

        log.info("pipe() user=%s chat=%s msg=%r", user_id, chat_id, user_message[:80])

        session: Optional[GrpcSession] = self._sessions.get(session_key)

        if session and session.is_alive() and session.pending_action:
            log.info("Routing reply to pending action: %r", user_message)
            self._run(session.send_input(user_message), timeout=10)

        elif session and session.is_alive():
            log.info("Continuing live session")
            self._run(session.send_message(user_message), timeout=10)

        else:
            if session:
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

        out_q: Queue = Queue()

        asyncio.run_coroutine_threadsafe(
            session.drain_to(out_q), self._loop
        )

        did_yield = False
        while True:
            try:
                event_type, data = out_q.get(timeout=300)
            except Empty:
                yield "\n\n**Timeout:** agente sem resposta por 5 minutos.\n"
                break

            if event_type is _DONE:
                if isinstance(data, str):
                    yield f"\n\n**Erro do agente:** {data}\n"
                    did_yield = True
                elif not did_yield:
                    # gRPC enviou `done` sem nenhum `text_chunk` — o stream ficava vazio e a BD sem mensagem do assistente
                    yield (
                        "**O agente não devolveu texto.** "
                        "Confirma `OPENROUTER_API_KEY`, o modelo e se o sandbox está a correr; vê os logs do container do agente.\n"
                    )
                    did_yield = True
                if session_key in self._sessions:
                    del self._sessions[session_key]
                break

            elif event_type == "text":
                did_yield = True
                yield data

            elif event_type == "action":
                action: PendingAction = data
                did_yield = True
                yield _format_action(action)
                break

            elif event_type == "timeout":
                yield "\n\n**Timeout:** agente demorou muito para responder.\n"
                break

    async def _gc_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(300)
                dead = [k for k, s in self._sessions.items() if not s.is_alive()]
                for k in dead:
                    await self._sessions.pop(k).close()
                if self._docker:
                    await self._docker.gc_expired()
            except asyncio.CancelledError:
                break
            except Exception:
                log.exception("GC loop error")
