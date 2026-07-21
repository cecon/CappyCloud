"""Conversation and messaging use cases — business logic for chat management."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import cast

from app.application.use_cases import _attachments_helpers as _att
from app.application.use_cases._conversation_crud import (
    CreateConversation,
    ListConversations,
    ListMessages,
)
from app.application.use_cases._conversation_titles import DEFAULT_TITLE, TITLE_MAX_LEN
from app.application.use_cases._payload_diagnostics import sanitize_payload_diagnostics
from app.application.use_cases._stream_helpers import (
    build_pipeline_body,
    command_result_payload,
    command_start_payload,
    compute_cost,
    enrich_repos_for_pipeline,
    ensure_repo_ids,
    inject_diff_comments,
)
from app.application.use_cases.user_workspaces import (
    EnsureUserRepositoryWorkspace,
    UserWorkspaceAccessDeniedError,
    UserWorkspaceNotFoundError,
)
from app.domain.entities import Conversation, Message, User, UserRole
from app.domain.value_objects import validate_permission_mode
from app.ports.agent import AgentPort
from app.ports.repositories import (
    AiModelCapabilityLookup,
    AttachmentRepository,
    ConversationRepository,
    MessageRepository,
    RepositoryRepository,
)
from app.ports.services import AttachmentStorage
from app.ports.user_access import AiModelAccessPolicy

__all__ = [
    "CreateConversation",
    "ListConversations",
    "ListMessages",
    "StreamMessage",
]

_SSE_HEARTBEAT_INTERVAL_S = 10.0
_SSE_INITIAL_FLUSH_BYTES = 2048


def _sse_comment(message: str, *, padding: int = 0) -> bytes:
    suffix = " " * max(0, padding)
    return f": {message}{suffix}\n\n".encode()


def _sse_payload(payload: dict) -> bytes:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()


def _next_chunk(gen):
    try:
        return next(gen)
    except StopIteration:
        return None


class StreamMessage:
    def __init__(
        self,
        conversations: ConversationRepository,
        messages: MessageRepository,
        agent: AgentPort,
        repositories: RepositoryRepository | None = None,
        attachments: AttachmentRepository | None = None,
        attachment_storage: AttachmentStorage | None = None,
        model_caps: AiModelCapabilityLookup | None = None,
        model_access: AiModelAccessPolicy | None = None,
        user_workspaces: EnsureUserRepositoryWorkspace | None = None,
    ) -> None:
        self._conversations = conversations
        self._messages = messages
        self._agent = agent
        self._repositories = repositories
        self._attachments = attachments
        self._storage = attachment_storage
        self._model_caps = model_caps
        self._model_access = model_access
        self._user_workspaces = user_workspaces

    async def execute(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        content: str,
        model_id: str = "cappycloud",
        user_role: UserRole = UserRole.USER,
        cursor: int | None = None,
        override_model: str | None = None,
        attachment_ids: list[uuid.UUID] | None = None,
        permission_mode: str | None = None,
        action_reply: bool = False,
    ) -> AsyncGenerator[bytes]:
        conv = await self._conversations.get(conversation_id, user_id)
        if not conv:
            raise LookupError("Conversa não encontrada.")

        resolved_permission_mode = validate_permission_mode(permission_mode or conv.permission_mode)
        should_update_conversation = False
        if conv.permission_mode != resolved_permission_mode:
            conv.permission_mode = resolved_permission_mode
            should_update_conversation = True

        attachments_payload: list[dict] | None = None
        injected_prompt = await inject_diff_comments(conversation_id, content)
        effective_model = await self._resolve_model(user_id, user_role, override_model)
        resolved_model_uuid = await self._resolve_model_uuid(user_id, user_role, effective_model)
        if resolved_model_uuid and conv.ai_model_id != resolved_model_uuid:
            conv.ai_model_id = resolved_model_uuid
            should_update_conversation = True

        if attachment_ids and not action_reply:
            use_native = await self._can_send_native_vision(effective_model)
            if use_native:
                attachments_payload = await self._load_attachment_bytes(
                    conversation_id, attachment_ids
                )
            else:
                injected_prompt = await self._inject_attachments(
                    conversation_id, attachment_ids, injected_prompt
                )
            injected_prompt = await self._inject_artifact_chunks(
                conversation_id, attachment_ids, content, injected_prompt
            )

        if not action_reply:
            await self._messages.save(
                Message(
                    id=uuid.uuid4(),
                    conversation_id=conv.id,
                    role="user",
                    content=content,
                )
            )

        if not action_reply and conv.title == DEFAULT_TITLE:
            conv.title = content[:TITLE_MAX_LEN] + ("…" if len(content) > TITLE_MAX_LEN else "")
            should_update_conversation = True

        if should_update_conversation:
            await self._conversations.update(conv)

        history = await self._messages.list_by_conversation(conversation_id)
        messages_payload = [{"role": m.role, "content": m.content} for m in history]

        await self._ensure_repo_ids(conv)
        pipeline_body = await self._build_pipeline_body(
            conv,
            user_id,
            user_role,
            cursor,
            effective_model,
            attachments_payload,
        )
        pipeline_body["action_reply"] = action_reply

        return self._stream_chunks(
            injected_prompt,
            model_id,
            messages_payload,
            pipeline_body,
            conversation_id,
            user_id,
            user_role,
            effective_model,
        )

    async def _can_send_native_vision(self, override_model: str | None) -> bool:
        return await _att.can_send_native_vision(self._model_caps, override_model)

    async def _resolve_model(
        self,
        user_id: uuid.UUID,
        user_role: UserRole,
        override_model: str | None,
    ) -> str | None:
        if self._model_access is None:
            return override_model
        return await self._model_access.resolve_model_for_user(user_id, user_role, override_model)

    async def _resolve_model_uuid(
        self,
        user_id: uuid.UUID,
        user_role: UserRole,
        model_id: str | None,
    ) -> uuid.UUID | None:
        resolver = cast(
            Callable[[uuid.UUID, UserRole, str | None], Awaitable[uuid.UUID | None]] | None,
            getattr(self._model_access, "resolve_model_uuid_for_user", None),
        )
        if resolver is None:
            return None
        return await resolver(user_id, user_role, model_id)

    async def _load_attachment_bytes(
        self, conversation_id: uuid.UUID, attachment_ids: list[uuid.UUID]
    ) -> list[dict] | None:
        return await _att.load_attachment_bytes(
            self._attachments, self._storage, conversation_id, attachment_ids
        )

    async def _inject_attachments(
        self,
        conversation_id: uuid.UUID,
        attachment_ids: list[uuid.UUID] | None,
        prompt: str,
    ) -> str:
        return await _att.inject_attachments(
            self._attachments, conversation_id, attachment_ids, prompt
        )

    async def _inject_artifact_chunks(
        self,
        conversation_id: uuid.UUID,
        attachment_ids: list[uuid.UUID] | None,
        query: str,
        prompt: str,
    ) -> str:
        return await _att.inject_artifact_chunks(
            self._attachments, conversation_id, attachment_ids, query, prompt
        )

    async def _ensure_repo_ids(self, conv: Conversation) -> None:
        await ensure_repo_ids(self._repositories, self._conversations, conv)

    async def _build_pipeline_body(
        self,
        conv: Conversation,
        user_id: uuid.UUID,
        user_role: UserRole,
        cursor: int | None,
        override_model: str | None = None,
        attachments_payload: list[dict] | None = None,
    ) -> dict:
        enriched = await enrich_repos_for_pipeline(self._repositories, conv.repos)
        enriched = await self._attach_user_workspaces(enriched, user_id, user_role)
        return build_pipeline_body(
            conv, enriched, user_id, cursor, override_model, attachments_payload
        )

    async def _attach_user_workspaces(
        self,
        repos: list[dict],
        user_id: uuid.UUID,
        user_role: UserRole,
    ) -> list[dict]:
        if self._user_workspaces is None:
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
                workspace = await self._user_workspaces.execute(
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

    async def _stream_chunks(
        self,
        content: str,
        model_id: str,
        messages_payload: list[dict],
        pipeline_body: dict,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        user_role: UserRole,
        selected_model: str | None,
    ) -> AsyncGenerator[bytes]:
        accumulated_text: list[str] = []
        accumulated_error: list[str] = []
        usage: dict = {}
        latest_payload_diagnostics: dict[str, object] | None = None
        assistant_saved = False
        gen = self._agent.pipe(content, model_id, messages_payload, pipeline_body)

        async def save_assistant_once() -> None:
            nonlocal assistant_saved, latest_payload_diagnostics
            if assistant_saved:
                return
            assistant_saved = True
            assistant_text = "".join(accumulated_text).strip()
            cost_usd = await self._compute_cost(usage)
            if assistant_text:
                await self._messages.save(
                    Message(
                        id=uuid.uuid4(),
                        conversation_id=conversation_id,
                        role="assistant",
                        content=assistant_text,
                        model_used=usage.get("model_used") or None,
                        prompt_tokens=int(usage.get("prompt_tokens") or 0),
                        completion_tokens=int(usage.get("completion_tokens") or 0),
                        cost_usd=cost_usd,
                        payload_diagnostics=latest_payload_diagnostics,
                    )
                )
            elif accumulated_error:
                await self._messages.save(
                    Message(
                        id=uuid.uuid4(),
                        conversation_id=conversation_id,
                        role="assistant",
                        content="**Erro:** " + " ".join(accumulated_error),
                        payload_diagnostics=latest_payload_diagnostics,
                    )
                )

        yield _sse_comment("stream-open", padding=_SSE_INITIAL_FLUSH_BYTES)
        yield _sse_payload(
            {
                "type": "status",
                "message": "Conexão com o agente aberta.",
            }
        )

        while True:
            next_chunk_task = asyncio.create_task(asyncio.to_thread(_next_chunk, gen))
            while True:
                try:
                    chunk = await asyncio.wait_for(
                        asyncio.shield(next_chunk_task),
                        timeout=_SSE_HEARTBEAT_INTERVAL_S,
                    )
                    break
                except TimeoutError:
                    yield _sse_comment("heartbeat")
            if chunk is None:
                break
            line = chunk.strip()
            save_before_yield = False
            stop_after_yield = False
            output_chunk = chunk
            if line.startswith("data: "):
                try:
                    evt = json.loads(line[6:])
                    evt_type = evt.get("type")
                    if evt_type == "text":
                        accumulated_text.append(evt.get("content", ""))
                    elif evt_type == "error":
                        accumulated_error.append(evt.get("message", ""))
                    elif evt_type == "payload_diagnostic":
                        diagnostics = sanitize_payload_diagnostics(evt.get("diagnostics"))
                        if diagnostics is None:
                            continue
                        latest_payload_diagnostics = diagnostics
                        output_chunk = _sse_payload(
                            {
                                "type": "payload_diagnostic",
                                "diagnostics": diagnostics,
                            }
                        ).decode("utf-8")
                    elif evt_type == "command_start":
                        output_chunk = _sse_payload(command_start_payload(evt)).decode("utf-8")
                    elif evt_type == "command_result":
                        output_chunk = _sse_payload(command_result_payload(evt)).decode("utf-8")
                    elif evt_type == "done":
                        # O TaskRunner enriquece o evento done com tokens/modelo
                        # para que possamos persistir o uso na mensagem assistant.
                        model_used = str(evt.get("model_used") or "")
                        if (
                            selected_model
                            and model_used
                            and model_used != selected_model
                            and not await self._final_model_is_authorized(
                                user_id, user_role, model_used
                            )
                        ):
                            message = (
                                "O runtime tentou usar um modelo de fallback nao "
                                "autorizado para esta conversa. Selecione um modelo "
                                "autorizado e tente novamente."
                            )
                            accumulated_text.clear()
                            accumulated_error.append(message)
                            output_chunk = _sse_payload(
                                {"type": "error", "message": message}
                            ).decode("utf-8")
                            save_before_yield = True
                            stop_after_yield = True
                        else:
                            output_chunk = _sse_payload(
                                {
                                    "type": "done",
                                    "model_used": model_used,
                                    "prompt_tokens": int(evt.get("prompt_tokens") or 0),
                                    "completion_tokens": int(evt.get("completion_tokens") or 0),
                                    **(
                                        {"fallback": evt["fallback"]}
                                        if isinstance(evt.get("fallback"), dict)
                                        else {}
                                    ),
                                }
                            ).decode("utf-8")
                        usage = {
                            "model_used": model_used,
                            "prompt_tokens": int(evt.get("prompt_tokens") or 0),
                            "completion_tokens": int(evt.get("completion_tokens") or 0),
                        }
                        save_before_yield = True
                except Exception:
                    pass
            if save_before_yield:
                await save_assistant_once()
            yield output_chunk.encode("utf-8")
            if stop_after_yield:
                return

        await save_assistant_once()

    async def _compute_cost(self, usage: dict) -> float:
        return await compute_cost(self._messages, usage)

    async def _final_model_is_authorized(
        self, user_id: uuid.UUID, user_role: UserRole, model_id: str
    ) -> bool:
        if self._model_access is None:
            return True
        try:
            resolved = await self._model_access.resolve_model_for_user(user_id, user_role, model_id)
        except PermissionError:
            return False
        return resolved == model_id
