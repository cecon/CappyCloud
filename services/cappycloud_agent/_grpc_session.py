"""
Persistent, resumable gRPC session for a single (user_id, chat_id).

Runs the openclaude bidirectional gRPC stream as a long-lived asyncio Task.
The session is PAUSED when an ActionRequired event arrives, and RESUMED
when the user provides their answer via the next pipe() call.

Lifecycle:
  1. GrpcSession.start(message)     → seeds the request queue, starts the Task
  2. GrpcSession.drain_to(q)        → called by pipe() to stream output into a Queue
  3. ActionRequired arrives          → drain_to() stops; session stays alive, paused
  4. GrpcSession.send_input(reply)  → user answered; resumes the Task
  5. GrpcSession.send_message(msg)  → new conversation turn (no pending action)
  6. done / error event             → Task ends; session marked dead

Generated stubs (openclaude_pb2) must be on PYTHONPATH (e.g. /app in Docker).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from queue import Queue
from typing import Optional

import grpc.aio
import openclaude_pb2  # type: ignore[import-not-found]
import openclaude_pb2_grpc  # type: ignore[import-not-found]

log = logging.getLogger(__name__)

# Sentinel placed in the output queue to signal end-of-stream
_DONE = object()


@dataclass
class PendingAction:
    """An ActionRequired event that needs a user response before the stream continues."""

    prompt_id: str
    question: str
    action_type: int  # 0 = CONFIRM_COMMAND (yes/no), 1 = REQUEST_INFORMATION (free text)
    choices: list[str] | None = None  # Parsed options when question contains [A / B / C]

    @property
    def is_confirmation(self) -> bool:
        return self.action_type == 0


def _parse_choices(question: str) -> list[str] | None:
    """
    Extract bracket-formatted choices from a question string.

    Example: "Qual módulo? [PDV / Financeiro / Relatórios]" → ["PDV", "Financeiro", "Relatórios"]
    """
    import re
    m = re.search(r"\[([^\]]+)\]", question)
    if not m:
        return None
    parts = [c.strip() for c in re.split(r"/|,|\|", m.group(1)) if c.strip()]
    return parts if len(parts) > 1 else None


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
        self._channel = grpc.aio.insecure_channel(f"{self._ip}:{self._port}")
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
                        choices=_parse_choices(ar.question),
                    )
                    self.pending_action = action
                    await self._out_queue.put(("action_required", action))

                elif event == "done":
                    # Alguns builds do openclaude só preenchem `full_text` no evento final,
                    # sem enviar `text_chunk` — antes ignorávamos isso e o chat ficava vazio.
                    done = msg.done
                    full = (done.full_text or "").strip()
                    if full and not streamed_text:
                        await self._out_queue.put(("text", full))
                        streamed_text = True
                    # 0 tokens + no text = LLM API call never happened (rate limit / quota)
                    if not streamed_text and done.prompt_tokens == 0 and done.completion_tokens == 0:
                        log.warning(
                            "[%s] Done with 0 tokens and no text — LLM call likely failed (rate limit or quota)",
                            self._session_id,
                        )
                        await self._out_queue.put((
                            "error",
                            "O modelo não gerou resposta (possível rate limit do OpenRouter). "
                            "Aguarda alguns segundos e tenta novamente, ou altera o modelo em OPENROUTER_MODEL.",
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
            log.error("[%s] gRPC error: %s", self._session_id, exc.details())
            await self._out_queue.put(("error", exc.details()))
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
