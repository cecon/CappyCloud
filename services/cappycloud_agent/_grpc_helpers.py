"""Helpers for gRPC session management: types, connection logic, and parsing."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass

import grpc.aio

log = logging.getLogger(__name__)


@dataclass
class PendingAction:
    """An ActionRequired event that needs a user response before the stream continues."""

    prompt_id: str
    question: str
    action_type: (
        int  # 0 = CONFIRM_COMMAND (yes/no), 1 = REQUEST_INFORMATION (free text)
    )
    choices: list[str] | None = None

    @property
    def is_confirmation(self) -> bool:
        return self.action_type == 0


def parse_choices(question: str) -> list[str] | None:
    """Extract bracket-formatted choices: "[A / B / C]" -> ["A", "B", "C"]."""
    m = re.search(r"\[([^\]]+)\]", question)
    if not m:
        return None
    parts = [c.strip() for c in re.split(r"/|,|\|", m.group(1)) if c.strip()]
    return parts if len(parts) > 1 else None


async def connect_with_retry(
    host: str,
    port: int,
    session_id: str,
    retries: int = 4,
) -> grpc.aio.Channel:
    """Open a gRPC channel with keepalive, retrying on transient failures."""
    delays = [1.0, 2.0, 4.0]
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            channel = grpc.aio.insecure_channel(
                f"{host}:{port}",
                options=[
                    ("grpc.keepalive_time_ms", 10_000),
                    ("grpc.keepalive_timeout_ms", 5_000),
                    ("grpc.keepalive_permit_without_calls", True),
                ],
            )
            await asyncio.wait_for(channel.channel_ready(), timeout=8.0)
            return channel
        except Exception as exc:
            last_exc = exc
            log.warning(
                "[%s] gRPC channel not ready (attempt %d/%d): %s",
                session_id,
                attempt + 1,
                retries,
                exc,
            )
            if attempt < len(delays):
                await asyncio.sleep(delays[attempt])
    raise RuntimeError(
        f"Não foi possível conectar ao sandbox gRPC após {retries} "
        f"tentativas ({host}:{port}). Último erro: {last_exc}"
    )


SESSION_START_ERROR = (
    "O agente não conseguiu iniciar a sessão. "
    "Possíveis causas: worktree não criado (branch base não existe), "
    "path de sessão inválido, ou erro no modelo. "
    "Verifique se o repositório e branch estão configurados correctamente."
)

GRPC_CONNECTION_LOST = (
    "Conexão com o sandbox perdida. Envie sua mensagem novamente para reconectar."
)

GRPC_UNEXPECTED_END = "O agente encerrou a conexão inesperadamente (possível rate limit ou timeout do modelo)."
