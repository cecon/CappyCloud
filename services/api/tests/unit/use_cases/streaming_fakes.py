"""Fakes e helpers compartilhados pelos testes de streaming de conversa."""

import json
import time
import uuid
from collections.abc import Generator
from typing import Any

from app.domain.entities import UserRole
from app.ports.user_access import AiModelAccessPolicy

from tests.conftest import FakeAgent


class _FakeModelAccessPolicy(AiModelAccessPolicy):
    def __init__(self, resolved: str = "openrouter/free", deny: bool = False) -> None:
        self.resolved = resolved
        self.deny = deny
        self.calls: list[tuple[uuid.UUID, UserRole, str | None]] = []

    async def resolve_model_for_user(
        self,
        user_id: uuid.UUID,
        role: UserRole,
        requested_model_id: str | None,
    ) -> str:
        self.calls.append((user_id, role, requested_model_id))
        if self.deny:
            raise PermissionError("Modelo bloqueado")
        return self.resolved


class _SelectiveModelAccessPolicy(AiModelAccessPolicy):
    def __init__(self, allowed: set[str]) -> None:
        self.allowed = allowed
        self.calls: list[tuple[uuid.UUID, UserRole, str | None]] = []

    async def resolve_model_for_user(
        self,
        user_id: uuid.UUID,
        role: UserRole,
        requested_model_id: str | None,
    ) -> str:
        self.calls.append((user_id, role, requested_model_id))
        if requested_model_id and requested_model_id in self.allowed:
            return requested_model_id
        raise PermissionError("Modelo bloqueado")


class _CapturingAgent(FakeAgent):
    def __init__(self) -> None:
        super().__init__()
        self.last_body: dict | None = None

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: list[dict[str, Any]],
        body: dict[str, Any],
    ) -> Generator[str]:
        self.last_body = body
        yield from super().pipe(user_message, model_id, messages, body)


class _SlowAgent(FakeAgent):
    def __init__(self, delay_s: float, response: str = FakeAgent.DEFAULT_RESPONSE) -> None:
        super().__init__(response)
        self._delay_s = delay_s

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: list[dict[str, Any]],
        body: dict[str, Any],
    ) -> Generator[str]:
        time.sleep(self._delay_s)
        yield from super().pipe(user_message, model_id, messages, body)


class _EventAgent(FakeAgent):
    def __init__(self, events: list[dict[str, Any]]) -> None:
        super().__init__()
        self._events = events

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: list[dict[str, Any]],
        body: dict[str, Any],
    ) -> Generator[str]:
        del user_message, model_id, messages, body
        for event in self._events:
            yield f"data: {json.dumps(event)}\n\n"


def _json_payloads(chunks: list[bytes]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for chunk in chunks:
        if not chunk.startswith(b"data: "):
            continue
        payloads.append(json.loads(chunk[6:]))
    return payloads
