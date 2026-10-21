"""Conversation and messaging use cases — business logic for chat management."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator

from app.application.use_cases import _attachments_helpers as _att
from app.application.use_cases._conversation_crud import (
    CreateConversation,
    ListConversations,
    ListMessages,
)
from app.application.use_cases._conversation_titles import DEFAULT_TITLE, TITLE_MAX_LEN
from app.application.use_cases._stream_helpers import (
    build_pipeline_body,
    compute_cost,
    enrich_repos_for_pipeline,
    ensure_repo_ids,
    inject_diff_comments,
)
from app.application.use_cases._stream_message_support import (
    EventOutcome,
    StreamState,
    attach_user_workspaces,
    final_model_is_authorized,
    next_chunk,
    process_event,
    resolve_model_uuid,
    save_assistant_message,
    sse_comment,
    sse_payload,
)
from app.application.use_cases.user_workspaces import EnsureUserRepositoryWorkspace
from app.domain.entities import Conversation, Message, UserRole
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


_sse_comment = sse_comment
_sse_payload = sse_payload
_next_chunk = next_chunk


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
        execution_profile: str | None = None,
        action_reply: bool = False,
        model_from_runtime: bool = False,
    ) -> AsyncGenerator[bytes]:
        conv = await self._conversations.get(conversation_id, user_id)
        if not conv:
            raise LookupError("Conversa não encontrada.")

        resolved_permission_mode = validate_permission_mode(permission_mode or conv.permission_mode)
        should_update_conversation = False
        if conv.permission_mode != resolved_permission_mode:
            conv.permission_mode = resolved_permission_mode
            should_update_conversation = True

        reconnecting_stream = cursor is not None and not action_reply

        attachments_payload: list[dict] | None = None
        injected_prompt = await inject_diff_comments(conversation_id, content)
        # O agente sabe o chamado (cita no commit/PR); o histórico guarda só a mensagem.
        if conv.ticket_number and not action_reply:
            injected_prompt = f"[Chamado {conv.ticket_number}]\n\n{injected_prompt}"
        # Modelo do runtime (Claude CLI): não está no catálogo; a rota já validou a sandbox.
        if model_from_runtime:
            effective_model, resolved_model_uuid = override_model, None
        else:
            effective_model = await self._resolve_model(user_id, user_role, override_model)
            resolved_model_uuid = await self._resolve_model_uuid(
                user_id, user_role, effective_model
            )
        if resolved_model_uuid and conv.ai_model_id != resolved_model_uuid:
            conv.ai_model_id = resolved_model_uuid
            should_update_conversation = True

        if attachment_ids and not action_reply:
            # Claude lê imagens direto; o catálogo não conhece os modelos do Claude CLI.
            use_native = model_from_runtime or await self._can_send_native_vision(effective_model)
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

        if not action_reply and not reconnecting_stream:
            await self._messages.save(
                Message(
                    id=uuid.uuid4(),
                    conversation_id=conv.id,
                    role="user",
                    content=content,
                )
            )

        if not action_reply and not reconnecting_stream and conv.title == DEFAULT_TITLE:
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
            execution_profile,
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
        return await resolve_model_uuid(self._model_access, user_id, user_role, model_id)

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
        execution_profile: str | None = None,
    ) -> dict:
        enriched = await enrich_repos_for_pipeline(self._repositories, conv.repos)
        # Conversa de workspace parte da branch base do workspace, não do baseline por usuário.
        if not conv.workspace_id:
            enriched = await self._attach_user_workspaces(enriched, user_id, user_role)
        return build_pipeline_body(
            conv, enriched, user_id, cursor, override_model, attachments_payload, execution_profile
        )

    async def _attach_user_workspaces(
        self,
        repos: list[dict],
        user_id: uuid.UUID,
        user_role: UserRole,
    ) -> list[dict]:
        return await attach_user_workspaces(self._user_workspaces, repos, user_id, user_role)

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
        state = StreamState()
        gen = self._agent.pipe(content, model_id, messages_payload, pipeline_body)

        async def save_assistant_once() -> None:
            if state.assistant_saved:
                return
            state.assistant_saved = True
            cost_usd = await self._compute_cost(state.usage)
            await save_assistant_message(self._messages, conversation_id, state, cost_usd)

        async def is_authorized(model_used: str) -> bool:
            return await self._final_model_is_authorized(user_id, user_role, model_used)

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
            outcome = EventOutcome(output_chunk=chunk)
            if line.startswith("data: "):
                try:
                    evt = json.loads(line[6:])
                    await process_event(outcome, evt, state, selected_model, is_authorized)
                except Exception:
                    pass
            if outcome.skip:
                continue
            if outcome.save_before_yield:
                await save_assistant_once()
            yield outcome.output_chunk.encode("utf-8")
            if outcome.stop_after_yield:
                return

        await save_assistant_once()

    async def _compute_cost(self, usage: dict) -> float:
        return await compute_cost(self._messages, usage)

    async def _final_model_is_authorized(
        self, user_id: uuid.UUID, user_role: UserRole, model_id: str
    ) -> bool:
        return await final_model_is_authorized(self._model_access, user_id, user_role, model_id)
