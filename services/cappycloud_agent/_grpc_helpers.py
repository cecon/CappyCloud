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


GRPC_CONNECTION_LOST = (
    "Conexão com o sandbox perdida. Envie sua mensagem novamente para reconectar."
)

GRPC_UNEXPECTED_END = "O agente encerrou a conexão inesperadamente (possível rate limit ou timeout do modelo)."


def build_done_empty_error(
    *, model: str, session_id: str, working_directory: str
) -> str:
    """Mensagem detalhada para o caso `done` sem texto/tokens.

    Inclui o modelo realmente usado e o working_directory para que o utilizador
    consiga identificar a causa (key/provider/modelo BYOK vs worktree
    ausente/path inválido) sem ter de cavar nos logs.
    """
    return (
        f"O agente não devolveu resposta nem tokens. "
        f"Modelo: `{model}`. "
        f"Sessão: `{session_id}`. "
        f"Working directory: `{working_directory}`. "
        "Causas mais prováveis: "
        "(1) chave OpenRouter inválida ou modelo BYOK sem provider configurado; "
        "(2) modelo indisponível ou rate-limited; "
        "(3) `working_directory` inexistente dentro do sandbox; "
        "(4) o openclaude rejeitou o pedido. "
        "Para diagnosticar: `docker logs cappycloud-sandbox -n 200`."
    )


def build_worktree_missing_error(
    *, repo_slugs: list[str], working_directory: str, detail: str = ""
) -> str:
    """Erro emitido quando o worktree esperado não existe no sandbox."""
    repos = ", ".join(repo_slugs) if repo_slugs else "<sem repos>"
    base = (
        f"Worktree não foi materializado para os repositórios: {repos}. "
        f"Path esperado: `{working_directory}`. "
        "Causas mais prováveis: "
        "(1) a branch base não existe no remote; "
        "(2) o clone falhou silenciosamente no sandbox; "
        "(3) o `session_start.sh` abortou. "
        "Para diagnosticar: `docker logs cappycloud-sandbox -n 200`."
    )
    if detail:
        return f"{base} Detalhe: {detail}"
    return base
