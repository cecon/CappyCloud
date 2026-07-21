"""Helpers for gRPC session management: types, connection logic, and parsing."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass

import grpc.aio

log = logging.getLogger(__name__)

DEFAULT_PERMISSION_MODE = "bypass_permissions"
PERMISSION_MODES = {
    DEFAULT_PERMISSION_MODE,
    "accept_edits",
    "plan",
    "auto",
    "bypass_permissions",
}


@dataclass
class PendingAction:
    """An ActionRequired event that needs a user response before the stream continues."""

    prompt_id: str
    question: str
    action_type: (
        int  # 1 = CONFIRM_COMMAND (yes/no), 2 = REQUEST_INFORMATION (free text)
    )
    choices: list[str] | None = None

    @property
    def is_confirmation(self) -> bool:
        return self.action_type == 1


def parse_choices(question: str) -> list[str] | None:
    """Extract bracket-formatted choices: "[A / B / C]" -> ["A", "B", "C"]."""
    m = re.search(r"\[([^\]]+)\]", question)
    if not m:
        return None
    parts = [c.strip() for c in re.split(r"/|,|\|", m.group(1)) if c.strip()]
    return parts if len(parts) > 1 else None


def sanitize_permission_mode(value: object | None) -> str:
    """Return a supported request-scoped permission mode."""
    mode = str(value or "").strip()
    if mode in PERMISSION_MODES:
        return mode
    return DEFAULT_PERMISSION_MODE


def permission_warning_status_from_text(text: object) -> dict | None:
    """Detect OpenClaude's startup permission warning without leaking raw logs."""
    value = str(text or "").lower()
    if "classifier" not in value:
        return None
    if "permissive" not in value and "permission" not in value:
        return None
    if "skip" not in value and "bypass" not in value:
        return None
    return {
        "message": "OpenClaude confirmou aviso de permissões permissivas.",
        "metadata": {
            "permission_warning": {
                "runtime_confirmed": True,
                "source": "openclaude_startup_alert",
            }
        },
    }


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

_PROVIDER_API_ERROR_RE = re.compile(
    r"^API Error:\s*(?P<status>\d{3})\s*(?P<payload>\{.*\})\s*$",
    re.DOTALL,
)


def provider_api_error_message(text: str) -> str | None:
    """Converte o texto cru de erro do provider em mensagem segura para a UI.

    Alguns providers/OpenRouter devolvem falhas como um ``text_chunk`` contendo
    ``API Error: 429 {...}`` em vez de um evento gRPC de erro. Se deixarmos isso
    passar como texto normal, a UI mostra JSON cru, marca o agente como
    respondido e ainda pode expor campos internos como ``user_id``.
    """
    match = _PROVIDER_API_ERROR_RE.match(text.strip())
    if not match:
        return None

    status = match.group("status")
    raw_payload = match.group("payload")
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        safe = raw_payload.split('"user_id"', 1)[0].strip().rstrip(",{ ")
        return f"Provedor de IA retornou erro {status}: {safe[:400]}"

    error = payload.get("error") if isinstance(payload, dict) else {}
    if not isinstance(error, dict):
        return f"Provedor de IA retornou erro {status}."

    metadata = error.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    provider = str(metadata.get("provider_name") or "").strip()
    raw = str(metadata.get("raw") or error.get("message") or "").strip()
    code = str(error.get("code") or status)
    message = raw or "erro sem detalhe retornado pelo provedor"

    if " is temporarily rate-limited upstream" in message:
        model = message.split(" is temporarily rate-limited upstream", 1)[0]
        message = f"{model} está temporariamente limitado no provedor upstream"

    parts = [f"Provedor de IA retornou erro {code}: {message}."]
    if provider:
        parts.append(f"Provider: {provider}.")
    parts.append("Troque o modelo ou tente novamente em instantes.")
    return " ".join(parts)


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
