"""Handlers puros que traduzem eventos do protobuf para tuplas da out_queue.

Extraídos do ``_grpc_session._run`` para manter o orquestrador enxuto. Cada
handler devolve a tupla ``(event_type, payload)`` que vai directa para a
``asyncio.Queue`` interna.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from ._grpc_helpers import (
    PendingAction,
    build_done_empty_error,
    parse_choices,
    permission_warning_status_from_text,
)
from ._grpc_helpers import provider_api_error_message

log = logging.getLogger(__name__)

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


def text_chunk_event(msg: Any) -> tuple[str, dict]:
    text = str(msg.text_chunk.text or "")
    permission_warning = permission_warning_status_from_text(text)
    if permission_warning:
        return ("status", permission_warning)
    provider_error = provider_api_error_message(text)
    if provider_error:
        return ("error", {"message": provider_error})
    return ("text", {"content": text})


def tool_start_event(msg: Any, session_id: str) -> tuple[str, dict]:
    ts = msg.tool_start
    log.info("[%s] Tool: %s", session_id, ts.tool_name)
    return (
        "tool_start",
        {"name": ts.tool_name, "input": ts.arguments_json, "id": ts.tool_use_id},
    )


def tool_result_event(msg: Any) -> tuple[str, dict]:
    tr = msg.tool_result
    output = tr.output
    if isinstance(output, bytes | bytearray):
        output = bytes(output).decode("utf-8", errors="replace")
    return (
        "tool_result",
        {
            "name": tr.tool_name,
            "output": output,
            "is_error": tr.is_error,
            "id": tr.tool_use_id,
        },
    )


def command_start_event(msg: Any) -> tuple[str, dict]:
    command = getattr(msg, "command_start", None)
    return (
        "command_start",
        {
            "command": _safe_command_name(getattr(command, "command", "")),
            "label": _safe_summary(getattr(command, "label", "Comando iniciado")),
        },
    )


def command_result_event(msg: Any) -> tuple[str, dict]:
    result = getattr(msg, "command_result", None)
    status = str(getattr(result, "status", "") or "failed")
    if status not in {"started", "waiting_for_input", "completed", "unavailable", "failed", "cancelled"}:
        status = "failed"
    return (
        "command_result",
        {
            "command": _safe_command_name(getattr(result, "command", "")),
            "status": status,
            "summary": _safe_summary(getattr(result, "summary", "")),
            "details_markdown": _safe_summary(getattr(result, "details_markdown", "")),
        },
    )


def payload_diagnostic_event(msg: Any) -> tuple[str, dict] | None:
    diagnostic = getattr(msg, "payload_diagnostic", None)
    if diagnostic is None:
        return None

    categories: dict[str, dict[str, float | int | str]] = {}
    for category in getattr(diagnostic, "categories", []) or []:
        key = _safe_category_key(getattr(category, "key", ""))
        size_bytes = _safe_int(getattr(category, "size_bytes", 0))
        if size_bytes <= 0:
            continue
        current = categories.setdefault(
            key,
            {
                "key": key,
                "label": SAFE_PAYLOAD_CATEGORY_LABELS[key],
                "size_bytes": 0,
                "percentage": 0.0,
            },
        )
        current["size_bytes"] = int(current["size_bytes"]) + size_bytes

    total_size_bytes = _safe_int(getattr(diagnostic, "total_size_bytes", 0))
    if not categories and total_size_bytes <= 0:
        return None
    if categories:
        total_size_bytes = sum(int(item["size_bytes"]) for item in categories.values())

    ordered = sorted(
        categories.values(), key=lambda item: int(item["size_bytes"]), reverse=True
    )
    for item in ordered:
        item["percentage"] = (
            round((int(item["size_bytes"]) / total_size_bytes) * 1000) / 10
            if total_size_bytes > 0
            else 0.0
        )

    return (
        "payload_diagnostic",
        {
            "diagnostics": {
                "total_size_bytes": total_size_bytes,
                "categories": ordered,
                "source": _safe_source(getattr(diagnostic, "source", "")),
                "generated_at": _safe_generated_at(
                    getattr(diagnostic, "generated_at", "")
                ),
            }
        },
    )


def action_required_event(msg: Any) -> tuple[tuple[str, PendingAction], PendingAction]:
    """Devolve ``((event, pending), pending)`` — caller persiste o pending."""
    ar = msg.action_required
    pending = PendingAction(
        prompt_id=ar.prompt_id,
        question=ar.question,
        action_type=ar.type,
        choices=parse_choices(ar.question),
    )
    return (("action_required", pending), pending)


def done_event(
    msg: Any, *, session_id: str, model: str, wd: str, streamed_text: bool
) -> tuple[str, Any]:
    """Done com 0 tokens + sem texto = openclaude não chamou o LLM."""
    done = msg.done
    if not streamed_text and done.prompt_tokens == 0 and done.completion_tokens == 0:
        log.warning(
            "[%s] Done com 0 tokens/sem texto — modelo=%s wd=%s",
            session_id,
            model,
            wd,
        )
        return (
            "error",
            build_done_empty_error(
                model=model, session_id=session_id, working_directory=wd
            ),
        )
    final_model = _safe_model_id(
        getattr(done, "model_used", "")
        or getattr(done, "final_model", "")
        or getattr(done, "provider_model", "")
        or model
    )
    fallback_reason = _safe_fallback_reason(
        getattr(done, "fallback_reason", "") or getattr(done, "fallback", "")
    )
    log.info(
        "[%s] Done model=%s in=%d out=%d",
        session_id,
        final_model,
        done.prompt_tokens,
        done.completion_tokens,
    )
    payload: dict[str, Any] = {
        "prompt_tokens": int(done.prompt_tokens),
        "completion_tokens": int(done.completion_tokens),
        "model_used": final_model,
    }
    if final_model != model:
        payload["fallback"] = {
            "selected_model": model,
            "final_model": final_model,
            "reason": fallback_reason or "runtime_model_changed",
        }
    return ("done", payload)


def final_text_fallback_event(
    msg: Any, *, streamed_text: bool
) -> tuple[str, dict] | None:
    """Converte ``done.full_text`` em texto quando não houve chunks no stream."""
    full_text = str(getattr(msg.done, "full_text", "") or "")
    if not full_text or streamed_text:
        return None
    return ("text", {"content": full_text})


def error_event(msg: Any, session_id: str) -> tuple[str, str]:
    log.error("[%s] Error [%s]: %s", session_id, msg.error.code, msg.error.message)
    return ("error", msg.error.message)


def _safe_category_key(value: Any) -> str:
    key = str(value or "").strip().lower()
    if key in SAFE_PAYLOAD_CATEGORY_LABELS:
        return key
    return "other"


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError, OverflowError):
        return 0


def _safe_source(value: Any) -> str:
    source = str(value or "openclaude").strip().lower()
    if source in {"openclaude", "cappycloud", "agent"}:
        return source
    return "openclaude"


def _safe_generated_at(value: Any) -> str:
    generated_at = str(value or "").strip()
    if _SAFE_DIAGNOSTIC_TEXT.fullmatch(generated_at):
        return generated_at
    return ""


def _safe_model_id(value: Any) -> str:
    model_id = str(value or "").strip()
    if _SAFE_MODEL_ID.fullmatch(model_id):
        return model_id
    return ""


def _safe_fallback_reason(value: Any) -> str:
    reason = str(value or "").strip().lower().replace(" ", "_")
    if _SAFE_DIAGNOSTIC_TEXT.fullmatch(reason):
        return reason
    return ""


def _safe_command_name(value: Any) -> str:
    command = str(value or "").strip()
    if re.fullmatch(r"/[A-Za-z0-9_.:-]{1,80}", command):
        return command
    return ""


def _safe_summary(value: Any) -> str:
    return str(value or "").replace("\x00", "")[:4000]
