"""Persistent, resumable gRPC session for a single (user_id, chat_id).

Generated stubs (openclaude_pb2) must be on PYTHONPATH (e.g. /app in Docker).
"""

from __future__ import annotations

import asyncio
import logging
from queue import Queue
from typing import Optional

import grpc.aio
import openclaude_pb2  # type: ignore[import-not-found]
import openclaude_pb2_grpc  # type: ignore[import-not-found]

from ._grpc_helpers import PendingAction, connect_with_retry, parse_choices

log = logging.getLogger(__name__)

_DONE = object()


class GrpcSession:
    """A single agent conversation session over a persistent gRPC stream."""

    def __init__(
        self,
        container_ip: str,
        grpc_port: int,
        session_id: str,
        model: str,
        working_directory: str = "/workspace",
    ) -> None:
        self._ip = container_ip
        self._port = grpc_port
        self._session_id = session_id
        self._model = model
        self._wd = working_directory

        # Client → gRPC server: ChatRequest and UserInput messages
        self._req_queue: asyncio.Queue = asyncio.Queue()
        # gRPC server → pipeline: (event_type, data) tuples
        self._out_queue: asyncio.Queue = asyncio.Queue()

        self.pending_action: Optional[PendingAction] = None
        self._task: Optional[asyncio.Task] = None
        self._channel: Optional[grpc.aio.Channel] = None

    # ── Startup ──────────────────────────────────────────────────

    async def start(self, message: str) -> None:
        """Open the gRPC channel, seed the first ChatRequest, launch the Task."""
        self._channel = await connect_with_retry(self._ip, self._port, self._session_id)
        stub = openclaude_pb2_grpc.AgentServiceStub(self._channel)

        await self._req_queue.put(
            openclaude_pb2.ClientMessage(
                request=openclaude_pb2.ChatRequest(
                    message=message,
                    working_directory=self._wd,
                    session_id=self._session_id,
                    model=self._model,
                )
            )
        )

        self._task = asyncio.create_task(self._run(stub))

    # ── User interactions ─────────────────────────────────────────

    async def send_input(self, reply: str) -> None:
        """Reply to the pending ActionRequired event and resume the stream."""
        if not self.pending_action:
            log.warning("[%s] send_input called but no pending action", self._session_id)
            return
        await self._req_queue.put(
            openclaude_pb2.ClientMessage(
                input=openclaude_pb2.UserInput(
                    reply=reply,
                    prompt_id=self.pending_action.prompt_id,
                )
            )
        )
        self.pending_action = None

    async def send_message(self, message: str) -> None:
        """Send a new message in an existing conversation (no pending action)."""
        await self._req_queue.put(
            openclaude_pb2.ClientMessage(
                request=openclaude_pb2.ChatRequest(
                    message=message,
                    working_directory=self._wd,
                    session_id=self._session_id,
                )
            )
        )

    # ── Output draining ───────────────────────────────────────────

    async def drain_to(self, out_q: Queue, loop_timeout: float = 300.0) -> None:
        """
        Pull events from the internal async queue and push them into *out_q*
        (a sync Queue consumed by pipe()'s generator).

        Stops when:
          - "done" or "error" event arrives  → puts _DONE into out_q
          - "action_required" event arrives  → puts (action, PendingAction) and stops
            (session stays alive; stream resumes when send_input() is called)
          - loop_timeout exceeded            → puts ("timeout", None)
        """
        try:
            while True:
                try:
                    event_type, data = await asyncio.wait_for(
                        self._out_queue.get(), timeout=loop_timeout
                    )
                except asyncio.TimeoutError:
                    out_q.put(("timeout", None))
                    return

                if event_type == "text":
                    out_q.put(("text", data))

                elif event_type in ("tool_start", "tool_result"):
                    out_q.put((event_type, data))

                elif event_type == "action_required":
                    # Pause — caller must call send_input() to continue
                    out_q.put(("action", data))
                    return

                elif event_type in ("done", "error"):
                    out_q.put((_DONE, data))
                    return

        except Exception as exc:
            log.exception("drain_to error")
            out_q.put(("text", f"\n\n**Erro interno:** {exc}\n"))
            out_q.put((_DONE, None))

    # ── State ─────────────────────────────────────────────────────

    def is_alive(self) -> bool:
        return self._task is not None and not self._task.done()

    async def close(self) -> None:
        if self._task:
            self._task.cancel()
        if self._channel:
            try:
                await self._channel.close()
            except Exception:
                pass

    # ── Internal gRPC task ───────────────────────────────────────

    _STOP = object()  # Sentinel to terminate the request generator

    async def _run(self, stub: openclaude_pb2_grpc.AgentServiceStub) -> None:
        """Long-running Task: pumps gRPC events into self._out_queue."""

        async def _requests():
            while True:
                item = await self._req_queue.get()
                if item is self._STOP:
                    return
                yield item

        streamed_text = False
        received_done = False
        try:
            async for msg in stub.Chat(_requests()):
                event = msg.WhichOneof("event")

                if event == "text_chunk":
                    streamed_text = True
                    await self._out_queue.put(("text", msg.text_chunk.text))

                elif event == "tool_start":
                    ts = msg.tool_start
                    log.info("[%s] Tool: %s", self._session_id, ts.tool_name)
                    await self._out_queue.put(("tool_start", {
                        "name": ts.tool_name,
                        "input": ts.arguments_json,
                        "id": ts.tool_use_id,
                    }))

                elif event == "tool_result":
                    tr = msg.tool_result
                    await self._out_queue.put(("tool_result", {
                        "name": tr.tool_name,
                        "output": tr.output,
                        "is_error": tr.is_error,
                        "id": tr.tool_use_id,
                    }))

                elif event == "action_required":
                    ar = msg.action_required
                    action = PendingAction(
                        prompt_id=ar.prompt_id,
                        question=ar.question,
                        action_type=ar.type,
                        choices=parse_choices(ar.question),
                    )
                    self.pending_action = action
                    await self._out_queue.put(("action_required", action))

                elif event == "done":
                    done = msg.done
                    # full_text foi removido do proto (reserved 1) — o texto já foi acumulado
                    # via text_chunk events. Se nenhum chunk chegou mas tokens = 0, é rate limit.
                    if not streamed_text and done.prompt_tokens == 0 and done.completion_tokens == 0:
                        log.warning(
                            "[%s] Done with 0 tokens and no text — LLM call likely failed (rate limit or quota)",
                            self._session_id,
                        )
                        await self._out_queue.put((
                            "error",
                            "O modelo não respondeu (rate limit ou cota esgotada). "
                            "Aguarde alguns segundos e tente novamente. "
                            "Para evitar este problema, use um modelo com limite maior em OPENROUTER_MODEL "
                            "(ex.: openai/gpt-4o-mini ou anthropic/claude-3-haiku).",
                        ))
                        received_done = True
                        return
                    log.info(
                        "[%s] Done — prompt_tokens=%d completion_tokens=%d",
                        self._session_id,
                        done.prompt_tokens,
                        done.completion_tokens,
                    )
                    received_done = True
                    await self._out_queue.put(("done", None))
                    return

                elif event == "error":
                    log.error(
                        "[%s] Error [%s]: %s",
                        self._session_id,
                        msg.error.code,
                        msg.error.message,
                    )
                    received_done = True
                    await self._out_queue.put(("error", msg.error.message))
                    return

            # gRPC stream closed without a done/error event (e.g. rate limit or server crash)
            if not received_done:
                log.warning("[%s] gRPC stream ended without done/error event", self._session_id)
                await self._out_queue.put(("error", "O agente encerrou a conexão inesperadamente (possível rate limit ou timeout do modelo)."))

        except grpc.aio.AioRpcError as exc:
            details = exc.details() or str(exc)
            log.error("[%s] gRPC error: %s", self._session_id, details)
            if "Socket closed" in details or "UNAVAILABLE" in exc.code().name:
                await self._out_queue.put((
                    "error",
                    "Conexão com o sandbox perdida. Envie sua mensagem novamente para reconectar.",
                ))
            else:
                await self._out_queue.put(("error", details))
        except asyncio.CancelledError:
            log.info("[%s] Session cancelled", self._session_id)
        except Exception as exc:
            log.exception("[%s] Unexpected error in gRPC task", self._session_id)
            await self._out_queue.put(("error", str(exc)))
        finally:
            if self._channel:
                try:
                    await self._channel.close()
                except Exception:
                    pass
