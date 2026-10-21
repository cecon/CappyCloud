"""Helpers do StreamMessage: SSE, workspaces por usuário e eventos do agente."""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import cast

from app.application.use_cases._payload_diagnostics import sanitize_payload_diagnostics
from app.application.use_cases._stream_helpers import (
    command_result_payload,
    command_start_payload,
    optional_tokens,
)
from app.application.use_cases.user_workspaces import (
    EnsureUserRepositoryWorkspace,
    UserWorkspaceAccessDeniedError,
    UserWorkspaceNotFoundError,
)
from app.domain.entities import Message, User, UserRole
from app.ports.repositories import MessageRepository
from app.ports.user_access import AiModelAccessPolicy

UNAUTHORIZED_FALLBACK_MESSAGE = (
    "O runtime tentou usar um modelo de fallback nao "
    "autorizado para esta conversa. Selecione um modelo "
    "autorizado e tente novamente."
)


def sse_comment(message: str, *, padding: int = 0) -> bytes:
    suffix = " " * max(0, padding)
    return f": {message}{suffix}\n\n".encode()


def sse_payload(payload: dict) -> bytes:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()


def next_chunk(gen):
    try:
        return next(gen)
    except StopIteration:
        return None


@dataclass
class StreamState:
    """Estado acumulado durante um stream do agente."""

    accumulated_text: list[str] = field(default_factory=list)
    accumulated_error: list[str] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    latest_payload_diagnostics: dict[str, object] | None = None
    assistant_saved: bool = False


@dataclass
class EventOutcome:
    """Resultado do processamento de um chunk SSE do agente."""

    output_chunk: str
    save_before_yield: bool = False
    stop_after_yield: bool = False
    skip: bool = False


async def save_assistant_message(
    messages: MessageRepository,
    conversation_id: uuid.UUID,
    state: StreamState,
    cost_usd: float,
) -> None:
    assistant_text = "".join(state.accumulated_text).strip()
    usage = state.usage
    if assistant_text:
        await messages.save(
            Message(
                id=uuid.uuid4(),
                conversation_id=conversation_id,
                role="assistant",
                content=assistant_text,
                model_used=usage.get("model_used") or None,
                prompt_tokens=int(usage.get("prompt_tokens") or 0),
                completion_tokens=int(usage.get("completion_tokens") or 0),
                cost_usd=cost_usd,
                cache_read_tokens=usage.get("cache_read_tokens"),
                cache_write_tokens=usage.get("cache_write_tokens"),
                payload_diagnostics=state.latest_payload_diagnostics,
                plan_usage=usage.get("plan_usage") or None,
            )
        )
    elif state.accumulated_error:
        await messages.save(
            Message(
                id=uuid.uuid4(),
                conversation_id=conversation_id,
                role="assistant",
                content="**Erro:** " + " ".join(state.accumulated_error),
                payload_diagnostics=state.latest_payload_diagnostics,
            )
        )


def done_payload(evt: dict, model_used: str) -> dict:
    return {
        "type": "done",
        "model_used": model_used,
        "prompt_tokens": int(evt.get("prompt_tokens") or 0),
        "completion_tokens": int(evt.get("completion_tokens") or 0),
        **({"fallback": evt["fallback"]} if isinstance(evt.get("fallback"), dict) else {}),
        **({"plan_usage": evt["plan_usage"]} if isinstance(evt.get("plan_usage"), dict) else {}),
    }


def done_usage(evt: dict, model_used: str) -> dict:
    return {
        "model_used": model_used,
        "prompt_tokens": int(evt.get("prompt_tokens") or 0),
        "completion_tokens": int(evt.get("completion_tokens") or 0),
        "plan_usage": (evt["plan_usage"] if isinstance(evt.get("plan_usage"), dict) else None),
        "cost_usd": evt.get("cost_usd"),
        "cache_read_tokens": optional_tokens(evt.get("cache_read_tokens")),
        "cache_write_tokens": optional_tokens(evt.get("cache_write_tokens")),
    }


async def process_event(
    outcome: EventOutcome,
    evt: dict,
    state: StreamState,
    selected_model: str | None,
    is_authorized: Callable[[str], Awaitable[bool]],
) -> None:
    """Processa um evento SSE já decodificado, ajustando ``outcome`` em ordem.

    As mutações acontecem passo a passo para que uma exceção no meio preserve
    o que já foi decidido (mesmo comportamento do laço original).
    """
    evt_type = evt.get("type")
    if evt_type == "text":
        state.accumulated_text.append(evt.get("content", ""))
    elif evt_type == "error":
        state.accumulated_error.append(evt.get("message", ""))
    elif evt_type == "payload_diagnostic":
        diagnostics = sanitize_payload_diagnostics(evt.get("diagnostics"))
        if diagnostics is None:
            outcome.skip = True
            return
        state.latest_payload_diagnostics = diagnostics
        outcome.output_chunk = sse_payload(
            {
                "type": "payload_diagnostic",
                "diagnostics": diagnostics,
            }
        ).decode("utf-8")
    elif evt_type == "command_start":
        outcome.output_chunk = sse_payload(command_start_payload(evt)).decode("utf-8")
    elif evt_type == "command_result":
        outcome.output_chunk = sse_payload(command_result_payload(evt)).decode("utf-8")
    elif evt_type == "done":
        # O TaskRunner enriquece o evento done com tokens/modelo
        # para que possamos persistir o uso na mensagem assistant.
        model_used = str(evt.get("model_used") or "")
        if (
            selected_model
            and model_used
            and model_used != selected_model
            and evt.get("runtime") != "claude_cli"
            and not await is_authorized(model_used)
        ):
            message = UNAUTHORIZED_FALLBACK_MESSAGE
            state.accumulated_text.clear()
            state.accumulated_error.append(message)
            outcome.output_chunk = sse_payload({"type": "error", "message": message}).decode(
                "utf-8"
            )
            outcome.save_before_yield = True
            outcome.stop_after_yield = True
        else:
            outcome.output_chunk = sse_payload(done_payload(evt, model_used)).decode("utf-8")
        state.usage = done_usage(evt, model_used)
        outcome.save_before_yield = True


async def resolve_model_uuid(
    model_access: AiModelAccessPolicy | None,
    user_id: uuid.UUID,
    user_role: UserRole,
    model_id: str | None,
) -> uuid.UUID | None:
    resolver = cast(
        Callable[[uuid.UUID, UserRole, str | None], Awaitable[uuid.UUID | None]] | None,
        getattr(model_access, "resolve_model_uuid_for_user", None),
    )
    if resolver is None:
        return None
    return await resolver(user_id, user_role, model_id)


async def final_model_is_authorized(
    model_access: AiModelAccessPolicy | None,
    user_id: uuid.UUID,
    user_role: UserRole,
    model_id: str,
) -> bool:
    if model_access is None:
        return True
    try:
        resolved = await model_access.resolve_model_for_user(user_id, user_role, model_id)
    except PermissionError:
        return False
    return resolved == model_id


async def attach_user_workspaces(
    user_workspaces: EnsureUserRepositoryWorkspace | None,
    repos: list[dict],
    user_id: uuid.UUID,
    user_role: UserRole,
) -> list[dict]:
    if user_workspaces is None:
        return repos
    current = User(id=user_id, email="", hashed_password="", role=user_role)
    enriched: list[dict] = []
    for repo in repos:
        next_repo = dict(repo)
        repo_id_raw = next_repo.get("repo_id")
        if not repo_id_raw:
            enriched.append(next_repo)
            continue
        try:
            workspace = await user_workspaces.execute(
                current_user=current,
                repository_id=uuid.UUID(str(repo_id_raw)),
                base_branch=str(next_repo.get("base_branch") or "main"),
            )
        except UserWorkspaceAccessDeniedError:
            raise
        except UserWorkspaceNotFoundError:
            raise
        except RuntimeError:
            enriched.append(next_repo)
            continue
        next_repo["source_workspace_path"] = workspace.workspace_path
        next_repo["user_workspace_id"] = str(workspace.id)
        next_repo["user_workspace_status"] = workspace.status
        enriched.append(next_repo)
    return enriched
