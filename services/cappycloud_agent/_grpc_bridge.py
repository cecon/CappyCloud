"""
gRPC Bridge: optional async stream helper for the openclaude bidirectional gRPC API.

Generated stubs (openclaude_pb2) must be on PYTHONPATH (e.g. /app in Docker).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Optional

import grpc
import grpc.aio
import openclaude_pb2  # type: ignore[import-not-found]
import openclaude_pb2_grpc  # type: ignore[import-not-found]

log = logging.getLogger(__name__)


class GrpcBridge:
    """Stateless bridge — one instance can serve concurrent sessions."""

    async def stream_chat(
        self,
        container_ip: str,
        grpc_port: int,
        message: str,
        session_id: str = "",
        working_directory: str = "/workspace",
        model: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Async generator that yields formatted strings for each gRPC event.

        Yields:
            str: Markdown-compatible text to stream back to the user.
        """
        target = f"{container_ip}:{grpc_port}"
        log.info("Connecting to openclaude gRPC at %s  session=%r", target, session_id)

        # Queue enables sending UserInput back on the same bidirectional stream
        request_queue: asyncio.Queue = asyncio.Queue()
        _STOP = object()  # Sentinel value to terminate the request generator

        async def _request_generator():
            """Produces ClientMessage objects from the queue."""
            while True:
                item = await request_queue.get()
                if item is _STOP:
                    return
                yield item

        # Seed the queue with the initial ChatRequest
        await request_queue.put(
            openclaude_pb2.ClientMessage(
                request=openclaude_pb2.ChatRequest(
                    message=message,
                    working_directory=working_directory,
                    session_id=session_id,
                    model=model or "",
                )
            )
        )

        channel = grpc.aio.insecure_channel(target)
        try:
            stub = openclaude_pb2_grpc.AgentServiceStub(channel)

            async for server_msg in stub.Chat(_request_generator()):
                event = server_msg.WhichOneof("event")

                if event == "text_chunk":
                    yield server_msg.text_chunk.text

                elif event == "tool_start":
                    ts = server_msg.tool_start
                    log.info("Tool call: %s  args=%s", ts.tool_name, ts.arguments_json[:120])

                elif event == "tool_result":
                    tr = server_msg.tool_result
                    if tr.is_error:
                        yield f"\n> ⚠️ Erro na ferramenta **{tr.tool_name}**: {tr.output}\n"
                    else:
                        log.debug("Tool result: %s  ok", tr.tool_name)

                elif event == "action_required":
                    ar = server_msg.action_required
                    log.info("Auto-approving: %r", ar.question)
                    await request_queue.put(
                        openclaude_pb2.ClientMessage(
                            input=openclaude_pb2.UserInput(
                                reply="y",
                                prompt_id=ar.prompt_id,
                            )
                        )
                    )

                elif event == "done":
                    log.info(
                        "Done — tokens: prompt=%d completion=%d",
                        server_msg.done.prompt_tokens,
                        server_msg.done.completion_tokens,
                    )
                    await request_queue.put(_STOP)
                    break

                elif event == "error":
                    err = server_msg.error
                    log.error("openclaude error [%s]: %s", err.code, err.message)
                    yield f"\n\n**Erro do agente ({err.code}):** {err.message}\n"
                    await request_queue.put(_STOP)
                    break

        except grpc.aio.AioRpcError as exc:
            log.error("gRPC call failed: %s", exc)
            yield f"\n\n**gRPC error:** {exc.details()}\n"
        finally:
            await channel.close()
