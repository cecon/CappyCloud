"""Handlers puros que traduzem eventos do protobuf para tuplas da out_queue.

Extraídos do ``_grpc_session._run`` para manter o orquestrador enxuto. Cada
handler devolve a tupla ``(event_type, payload)`` que vai directa para a
``asyncio.Queue`` interna.
"""

from __future__ import annotations

import logging
from typing import Any

from ._grpc_helpers import PendingAction, build_done_empty_error, parse_choices

log = logging.getLogger(__name__)


def text_chunk_event(msg: Any) -> tuple[str, dict]:
    return ("text", {"content": msg.text_chunk.text})


def tool_start_event(msg: Any, session_id: str) -> tuple[str, dict]:
    ts = msg.tool_start
    log.info("[%s] Tool: %s", session_id, ts.tool_name)
    return (
        "tool_start",
        {"name": ts.tool_name, "input": ts.arguments_json, "id": ts.tool_use_id},
    )


def tool_result_event(msg: Any) -> tuple[str, dict]:
    tr = msg.tool_result
    return (
        "tool_result",
        {
            "name": tr.tool_name,
            "output": tr.output,
            "is_error": tr.is_error,
            "id": tr.tool_use_id,
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
    log.info(
        "[%s] Done model=%s in=%d out=%d",
        session_id,
        model,
        done.prompt_tokens,
        done.completion_tokens,
    )
    return (
        "done",
        {
            "prompt_tokens": int(done.prompt_tokens),
            "completion_tokens": int(done.completion_tokens),
            "model_used": model,
        },
    )


def error_event(msg: Any, session_id: str) -> tuple[str, str]:
    log.error("[%s] Error [%s]: %s", session_id, msg.error.code, msg.error.message)
    return ("error", msg.error.message)
