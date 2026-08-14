"""Sanitizers for user-visible gRPC event payloads."""

from __future__ import annotations

import re
from typing import Any

SAFE_PAYLOAD_CATEGORY_LABELS = {
    "user_message": "Mensagem do usuario",
    "conversation_history": "Historico da conversa",
    "repository_context": "Contexto do repositorio",
    "attachments": "Anexos",
    "tool_results": "Resultados de ferramentas",
    "tool_schemas": "Ferramentas",
    "mcp_tool_schemas": "Ferramentas MCP",
    "runtime_context": "Contexto de runtime",
    "other": "Outros",
}

_SAFE_DIAGNOSTIC_TEXT = re.compile(r"^[A-Za-z0-9_.:+-]{1,64}$")
_SAFE_MODEL_ID = re.compile(r"^[A-Za-z0-9_.:/@+-]{1,256}$")


def safe_activity_state(value: Any) -> str:
    state = str(value or "")
    if state in {
        "loading",
        "streaming",
        "tool-running",
        "permission-request",
        "permission-timeout",
        "stalled",
        "canceled",
        "failed",
        "done",
    }:
        return state
    return "tool-running"


def safe_category_key(value: Any) -> str:
    key = str(value or "").strip().lower()
    if key in SAFE_PAYLOAD_CATEGORY_LABELS:
        return key
    return "other"


def safe_command_name(value: Any) -> str:
    command = str(value or "").strip()
    if re.fullmatch(r"/[A-Za-z0-9_.:-]{1,80}", command):
        return command
    return ""


def safe_fallback_reason(value: Any) -> str:
    reason = str(value or "").strip().lower().replace(" ", "_")
    if _SAFE_DIAGNOSTIC_TEXT.fullmatch(reason):
        return reason
    return ""


def safe_generated_at(value: Any) -> str:
    generated_at = str(value or "").strip()
    if _SAFE_DIAGNOSTIC_TEXT.fullmatch(generated_at):
        return generated_at
    return ""


def safe_identifier(value: Any) -> str | None:
    identifier = str(value or "").strip()
    if _SAFE_MODEL_ID.fullmatch(identifier):
        return identifier
    return None


def safe_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except TypeError, ValueError, OverflowError:
        return 0


def safe_model_id(value: Any) -> str:
    model_id = str(value or "").strip()
    if _SAFE_MODEL_ID.fullmatch(model_id):
        return model_id
    return ""


def safe_optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    parsed = safe_int(value)
    return parsed if parsed > 0 else 0


def safe_optional_percent(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        numeric = float(value)
    except TypeError, ValueError, OverflowError:
        return None
    return max(0.0, min(100.0, round(numeric, 1)))


def safe_source(value: Any) -> str:
    source = str(value or "openclaude").strip().lower()
    if source in {"openclaude", "cappycloud", "agent"}:
        return source
    return "openclaude"


def safe_summary(value: Any) -> str:
    return str(value or "").replace("\x00", "")[:4000]


def safe_user_text(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    return re.sub(r"[\r\n\t]+", " ", text)[:280]
