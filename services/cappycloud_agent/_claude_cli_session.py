"""Sessão de agente com o Claude Code oficial (runtime ``claude_cli``).

O session server do sandbox roda o turno com o Claude Agent SDK e devolve os
mesmos eventos que o openclaude emite via gRPC, em NDJSON
(``services/sandbox/claude_runtime_handler.js``). Esta classe implementa o
contrato ``AgentSession``: lê o stream, expõe ``pending_action`` e repassa
respostas e cancelamentos por HTTP.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import uuid
from contextlib import suppress

import httpx

from ._grpc_helpers import (
    GRPC_CONNECTION_LOST,
    GRPC_UNEXPECTED_END,
    PendingAction,
    sanitize_permission_mode,
)

log = logging.getLogger(__name__)

_TERMINAL_EVENTS = {"done", "error"}


def _attachments_payload(attachments: list[dict] | None) -> list[dict]:
    return [
        {
            "mime_type": att.get("mime_type", "application/octet-stream"),
            "original_filename": att.get("original_filename", ""),
            "data_base64": base64.b64encode(att["data"]).decode("ascii"),
        }
        for att in attachments or []
        if att.get("data")
    ]


class ClaudeCliSession:
    """Um turno do Claude CLI servido pelo session server do sandbox."""

    def __init__(
        self,
        host: str,
        session_port: int,
        conversation_key: str,
        model: str,
        working_directory: str,
        permission_mode: str = "bypass_permissions",
        internal_token: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = f"http://{host}:{session_port}"
        self._conversation_key = conversation_key
        self._model = model
        self._wd = working_directory
        self._permission_mode = sanitize_permission_mode(permission_mode)
        self._headers = {
            "X-Internal-Token": internal_token
            if internal_token is not None
            else os.getenv("INTERNAL_API_TOKEN", "")
        }
        self._transport = transport
        self._turn_id = uuid.uuid4().hex
        self._out_queue: asyncio.Queue = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self.pending_action: PendingAction | None = None

    def _client(self, timeout: httpx.Timeout) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._headers,
            timeout=timeout,
            transport=self._transport,
        )

    async def start(self, message: str, attachments: list[dict] | None = None) -> None:
        payload = {
            "turn_id": self._turn_id,
            "conversation_key": self._conversation_key,
            "prompt": message,
            "cwd": self._wd,
            "model": self._model,
            "permission_mode": self._permission_mode,
            "attachments": _attachments_payload(attachments),
        }
        self._task = asyncio.create_task(self._run(payload))

    async def next_event(self) -> tuple[str, object]:
        return await self._out_queue.get()

    async def send_input(self, reply: str) -> None:
        pending = self.pending_action
        if not pending:
            log.warning("[%s] send_input sem ação pendente", self._conversation_key)
            return
        self.pending_action = None
        async with self._client(httpx.Timeout(15.0)) as client:
            resp = await client.post(
                f"/claude/turns/{self._turn_id}/input",
                json={"prompt_id": pending.prompt_id, "reply": reply},
            )
        if resp.status_code != 200:
            log.warning(
                "[%s] resposta ao Claude CLI recusada: %s %s",
                self._conversation_key,
                resp.status_code,
                resp.text[:200],
            )

    async def send_message(self, message: str, attachments: list[dict] | None = None) -> None:
        # Cada mensagem nova vira um turno (task) próprio; o histórico segue
        # pelo `resume` do Claude CLI, guardado por conversation_key no sandbox.
        log.warning("[%s] send_message não suportado no runtime claude_cli", self._conversation_key)

    def is_alive(self) -> bool:
        return self._task is not None and not self._task.done()

    async def close(self) -> None:
        if self.is_alive():
            with suppress(httpx.HTTPError):
                async with self._client(httpx.Timeout(5.0)) as client:
                    await client.post(f"/claude/turns/{self._turn_id}/cancel")
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

    async def _run(self, payload: dict) -> None:
        # Sem timeout de leitura: o TaskRunner já controla silêncio do stream.
        timeout = httpx.Timeout(connect=10.0, read=None, write=30.0, pool=10.0)
        finished = False
        try:
            async with (
                self._client(timeout) as client,
                client.stream("POST", "/claude/turns", json=payload) as resp,
            ):
                if resp.status_code != 200:
                    body = (await resp.aread()).decode("utf-8", "replace")[:300]
                    await self._emit(
                        "error",
                        {"message": f"Claude CLI indisponível ({resp.status_code}): {body}"},
                    )
                    return
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        log.warning(
                            "[%s] linha NDJSON inválida: %r", self._conversation_key, line[:200]
                        )
                        continue
                    event_type = str(event.pop("type", ""))
                    if not event_type:
                        continue
                    await self._dispatch(event_type, event)
                    if event_type in _TERMINAL_EVENTS:
                        finished = True
                        return
            if not finished:
                await self._emit("error", {"message": GRPC_UNEXPECTED_END})
        except asyncio.CancelledError:
            raise
        except httpx.ConnectError:
            await self._emit(
                "error",
                {
                    "message": f"Não foi possível conectar ao sandbox em {self._base_url}. "
                    "Verifique se o cappycloud-sandbox está rodando."
                },
            )
        except httpx.HTTPError as exc:
            log.warning("[%s] stream do Claude CLI caiu: %s", self._conversation_key, exc)
            await self._emit("error", {"message": GRPC_CONNECTION_LOST})

    async def _dispatch(self, event_type: str, data: dict) -> None:
        if event_type == "action_required":
            action = PendingAction(
                prompt_id=str(data.get("prompt_id") or ""),
                question=str(data.get("question") or ""),
                action_type=int(data.get("action_type") or 1),
                choices=data.get("choices") or None,
            )
            self.pending_action = action
            await self._emit("action_required", action)
            return
        await self._emit(event_type, data)

    async def _emit(self, event_type: str, data: object) -> None:
        await self._out_queue.put((event_type, data))
