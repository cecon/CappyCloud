"""Contrato de uma sessão de agente consumida pelo TaskRunner.

Implementações: ``GrpcSession`` (openclaude via gRPC) e ``ClaudeCliSession``
(Claude Code oficial via Agent SDK no session server do sandbox). Ambas emitem
os mesmos ``(event_type, data)`` — text, tool_start, tool_result,
action_required (``PendingAction``), done, error, status — para que eventos,
timeline e histórico não dependam do runtime.
"""

from __future__ import annotations

from typing import Protocol

from ._grpc_helpers import PendingAction

AGENT_RUNTIME_OPENCLAUDE = "openclaude"
AGENT_RUNTIME_CLAUDE_CLI = "claude_cli"


class AgentSession(Protocol):
    pending_action: PendingAction | None

    async def start(self, message: str, attachments: list[dict] | None = None) -> None: ...

    async def next_event(self) -> tuple[str, object]: ...

    async def send_input(self, reply: str) -> None: ...

    async def send_message(self, message: str, attachments: list[dict] | None = None) -> None: ...

    def is_alive(self) -> bool: ...

    async def close(self) -> None: ...
