"""Handlers puros que traduzem eventos do protobuf para tuplas da out_queue.

Extraídos do ``_grpc_session._run`` para manter o orquestrador enxuto. Cada
handler devolve a tupla ``(event_type, payload)`` que vai directa para a
``asyncio.Queue`` interna.
"""

from __future__ import annotations

import logging
from typing import Any

from ._grpc_event_safety import (
    SAFE_PAYLOAD_CATEGORY_LABELS,
    safe_activity_state,
    safe_category_key,
    safe_command_name,
    safe_fallback_reason,
    safe_generated_at,
    safe_identifier,
    safe_int,
    safe_model_id,
    safe_optional_int,
    safe_optional_percent,
    safe_source,
    safe_summary,
    safe_user_text,
)
from ._grpc_helpers import (
    PendingAction,
    build_done_empty_error,
    parse_choices,
    permission_warning_status_from_text,
    provider_api_error_message,
)

log = logging.getLogger(__name__)


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
            "command": safe_command_name(getattr(command, "command", "")),
            "label": safe_summary(getattr(command, "label", "Comando iniciado")),
        },
    )


def command_result_event(msg: Any) -> tuple[str, dict]:
    result = getattr(msg, "command_result", None)
    status = str(getattr(result, "status", "") or "failed")
    if status not in {
        "started",
        "waiting_for_input",
        "completed",
        "unavailable",
        "failed",
        "cancelled",
    }:
        status = "failed"
    return (
        "command_result",
        {
            "command": safe_command_name(getattr(result, "command", "")),
            "status": status,
            "summary": safe_summary(getattr(result, "summary", "")),
            "details_markdown": safe_summary(getattr(result, "details_markdown", "")),
        },
    )


def payload_diagnostic_event(msg: Any) -> tuple[str, dict] | None:
    diagnostic = getattr(msg, "payload_diagnostic", None)
    if diagnostic is None:
        return None

    categories: dict[str, dict[str, float | int | str]] = {}
    for category in getattr(diagnostic, "categories", []) or []:
        key = safe_category_key(getattr(category, "key", ""))
        size_bytes = safe_int(getattr(category, "size_bytes", 0))
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

    total_size_bytes = safe_int(getattr(diagnostic, "total_size_bytes", 0))
    if not categories and total_size_bytes <= 0:
        return None
    if categories:
        total_size_bytes = sum(int(item["size_bytes"]) for item in categories.values())

    ordered = sorted(categories.values(), key=lambda item: int(item["size_bytes"]), reverse=True)
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
                "source": safe_source(getattr(diagnostic, "source", "")),
                "generated_at": safe_generated_at(getattr(diagnostic, "generated_at", "")),
            }
        },
    )


def context_progress_event(msg: Any) -> tuple[str, dict] | None:
    progress = getattr(msg, "context_progress", None)
    if progress is None:
        return None
    current_value = safe_optional_int(getattr(progress, "current_value", None))
    limit_value = safe_optional_int(getattr(progress, "limit_value", None))
    percent = safe_optional_percent(getattr(progress, "percent", None))
    if percent is None and current_value is not None and limit_value:
        percent = round((current_value / limit_value) * 1000) / 10
    return (
        "context_progress",
        {
            "label": safe_user_text(getattr(progress, "label", ""), "Processando contexto"),
            "current_value": current_value,
            "limit_value": limit_value,
            "percent": percent,
            "financial": False,
        },
    )


def subagent_group_event(msg: Any) -> tuple[str, dict] | None:
    group = getattr(msg, "subagent_group", None)
    if group is None:
        return None
    activities = []
    for activity in getattr(group, "activities", []) or []:
        activities.append(
            {
                "id": safe_identifier(getattr(activity, "id", "")) or "subagent",
                "name": safe_user_text(getattr(activity, "name", ""), "Subagente"),
                "state": safe_activity_state(getattr(activity, "state", "")),
                "detail": safe_user_text(getattr(activity, "detail", ""), ""),
            }
        )
    return (
        "subagent_group",
        {
            "parent_turn_id": safe_identifier(getattr(group, "parent_turn_id", "")),
            "label": safe_user_text(getattr(group, "label", ""), "Atividade auxiliar"),
            "collapsible": getattr(group, "collapsible", True) is not False,
            "activities": activities,
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
            build_done_empty_error(model=model, session_id=session_id, working_directory=wd),
        )
    final_model = safe_model_id(
        getattr(done, "model_used", "")
        or getattr(done, "final_model", "")
        or getattr(done, "provider_model", "")
        or model
    )
    fallback_reason = safe_fallback_reason(
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


def final_text_fallback_event(msg: Any, *, streamed_text: bool) -> tuple[str, dict] | None:
    """Converte ``done.full_text`` em texto quando não houve chunks no stream."""
    full_text = str(getattr(msg.done, "full_text", "") or "")
    if not full_text or streamed_text:
        return None
    return ("text", {"content": full_text})


def error_event(msg: Any, session_id: str) -> tuple[str, str]:
    log.error("[%s] Error [%s]: %s", session_id, msg.error.code, msg.error.message)
    return ("error", msg.error.message)
