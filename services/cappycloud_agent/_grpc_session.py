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

from . import _grpc_event_handlers as handlers
from ._grpc_helpers import (
    GRPC_CONNECTION_LOST,
    GRPC_UNEXPECTED_END,
    PendingAction,
    connect_with_retry,
)

log = logging.getLogger(__name__)

_DONE = object()


def _build_attachments_pb(attachments: list[dict] | None) -> list:
    """Constrói a lista ``Attachment`` do protobuf a partir de dicts.

    Aceita-se ``None``/``[]`` — devolve lista vazia (campo ``repeated`` no
    proto absorve sem erro). O fork do openclaude (patch ``multimodal-*``)
    converte cada item num bloco ``image`` e prepende-o à mensagem antes de
    chamar ``QueryEngine.submitMessage()``.
    """
    if not attachments:
        return []
    out = []
    for att in attachments:
        out.append(
            openclaude_pb2.Attachment(
                mime_type=att.get("mime_type", "application/octet-stream"),
                data=att["data"],
                original_filename=att.get("original_filename", ""),
            )
        )
    return out


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

    async def start(
        self,
        message: str,
        attachments: list[dict] | None = None,
    ) -> None:
        """Open the gRPC channel, seed the first ChatRequest, launch the Task.

        ``attachments``: lista de ``{"mime_type": str, "data": bytes,
        "original_filename": str}``. Quando vazia, o pedido viaja como antes.
        """
        self._channel = await connect_with_retry(self._ip, self._port, self._session_id)
        stub = openclaude_pb2_grpc.AgentServiceStub(self._channel)

        await self._req_queue.put(
            openclaude_pb2.ClientMessage(
                request=openclaude_pb2.ChatRequest(
                    message=message,
                    working_directory=self._wd,
                    session_id=self._session_id,
                    model=self._model,
                    attachments=_build_attachments_pb(attachments),
                )
            )
        )

        self._task = asyncio.create_task(self._run(stub))

    # ── User interactions ─────────────────────────────────────────

    async def send_input(self, reply: str) -> None:
        """Reply to the pending ActionRequired event and resume the stream."""
        if not self.pending_action:
            log.warning(
                "[%s] send_input called but no pending action", self._session_id
            )
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

    async def send_message(
        self,
        message: str,
        attachments: list[dict] | None = None,
    ) -> None:
        """Send a new message in an existing conversation (no pending action)."""
        await self._req_queue.put(
            openclaude_pb2.ClientMessage(
                request=openclaude_pb2.ChatRequest(
                    message=message,
                    working_directory=self._wd,
                    session_id=self._session_id,
                    attachments=_build_attachments_pb(attachments),
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
                    await self._out_queue.put(handlers.text_chunk_event(msg))

                elif event == "tool_start":
                    await self._out_queue.put(
                        handlers.tool_start_event(msg, self._session_id)
                    )

                elif event == "tool_result":
                    await self._out_queue.put(handlers.tool_result_event(msg))

                elif event == "action_required":
                    out, pending = handlers.action_required_event(msg)
                    self.pending_action = pending
                    await self._out_queue.put(out)

                elif event == "done":
                    received_done = True
                    await self._out_queue.put(
                        handlers.done_event(
                            msg,
                            session_id=self._session_id,
                            model=self._model,
                            wd=self._wd,
                            streamed_text=streamed_text,
                        )
                    )
                    return

                elif event == "error":
                    received_done = True
                    await self._out_queue.put(
                        handlers.error_event(msg, self._session_id)
                    )
                    return

            # gRPC stream closed without a done/error event (e.g. rate limit ou crash)
            if not received_done:
                log.warning(
                    "[%s] gRPC stream ended without done/error event", self._session_id
                )
                await self._out_queue.put(("error", GRPC_UNEXPECTED_END))

        except grpc.aio.AioRpcError as exc:
            details = exc.details() or str(exc)
            log.error("[%s] gRPC error: %s", self._session_id, details)
            if "Socket closed" in details or "UNAVAILABLE" in exc.code().name:
                await self._out_queue.put(("error", GRPC_CONNECTION_LOST))
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
