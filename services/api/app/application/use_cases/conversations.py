"""Conversation and messaging use cases — business logic for chat management.

No FastAPI, no SQLAlchemy. All dependencies injected via ports (ABCs).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator

from app.domain.entities import Conversation, Message
from app.ports.agent import AgentPort
from app.ports.repositories import (
    ConversationRepository,
    MessageRepository,
)

_TITLE_MAX_LEN = 80
_DEFAULT_TITLE = "Nova conversa"


def _next_chunk(gen):
    """Pull one chunk from a synchronous generator (for asyncio.to_thread)."""
    try:
        return next(gen)
    except StopIteration:
        return None


# ── Conversation use cases ────────────────────────────────────────────────────


class ListConversations:
    """Return all conversations for a user, newest first."""

    def __init__(self, conversations: ConversationRepository) -> None:
        self._conversations = conversations

    async def execute(self, user_id: uuid.UUID) -> list[Conversation]:
        return await self._conversations.list_by_user(user_id)


class CreateConversation:
    """Create a new conversation for a user."""

    def __init__(self, conversations: ConversationRepository) -> None:
        self._conversations = conversations

    async def execute(
        self,
        user_id: uuid.UUID,
        title: str | None = None,
        environment_id: uuid.UUID | None = None,
        base_branch: str | None = None,
    ) -> Conversation:
        conv = Conversation(
            id=uuid.uuid4(),
            user_id=user_id,
            title=title or _DEFAULT_TITLE,
            environment_id=environment_id,
            base_branch=base_branch,
        )
        return await self._conversations.save(conv)


class ListMessages:
    """Return message history for a conversation, verifying ownership."""

    def __init__(
        self,
        conversations: ConversationRepository,
        messages: MessageRepository,
    ) -> None:
        self._conversations = conversations
        self._messages = messages

    async def execute(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> list[Message]:
        """Return messages for conversation.

        Raises:
            LookupError: if conversation not found or not owned by user.
        """
        conv = await self._conversations.get(conversation_id, user_id)
        if not conv:
            raise LookupError("Conversa não encontrada.")
        return await self._messages.list_by_conversation(conversation_id)


class StreamMessage:
    """Orchestrate sending a user message and streaming the agent response.

    Responsibilities:
    1. Verify conversation ownership.
    2. Collect unbundled diff_comments and inject into the prompt.
    3. Persist the user message.
    4. Optionally auto-title the conversation.
    5. Call agent.pipe() — which dispatches a TaskRunner and streams agent_events.
    6. Yield SSE bytes to the HTTP layer.
    7. Persist the accumulated assistant response after streaming.

    The SSE stream includes a `cursor` field on each event (the agent_event.id).
    Clients that reconnect pass `cursor` so they receive only unseen events.

    Usage::

        stream = await use_case.execute(conv_id, user_id, content, cursor=last_event_id)
        return StreamingResponse(stream, media_type="text/event-stream")
    """

    def __init__(
        self,
        conversations: ConversationRepository,
        messages: MessageRepository,
        agent: AgentPort,
    ) -> None:
        self._conversations = conversations
        self._messages = messages
        self._agent = agent

    async def execute(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        content: str,
        model_id: str = "cappycloud",
        cursor: int | None = None,
    ) -> AsyncGenerator[bytes, None]:
        """Validate ownership, inject diff comments, persist user msg, stream events.

        Raises:
            LookupError: if conversation not found or not owned by user.
        """
        conv = await self._conversations.get(conversation_id, user_id)
        if not conv:
            raise LookupError("Conversa não encontrada.")

        # Collect and bundle pending diff_comments into the prompt
        injected_prompt = await self._inject_diff_comments(conversation_id, content)

        await self._messages.save(
            Message(
                id=uuid.uuid4(),
                conversation_id=conv.id,
                role="user",
                content=content,  # store original, not the injected version
            )
        )

        if conv.title == _DEFAULT_TITLE:
            conv.title = content[:_TITLE_MAX_LEN] + ("…" if len(content) > _TITLE_MAX_LEN else "")
            await self._conversations.update(conv)

        history = await self._messages.list_by_conversation(conversation_id)
        messages_payload = [{"role": m.role, "content": m.content} for m in history]

        base_branch = conv.base_branch or ""

        pipeline_body = {
            "user_id": str(user_id),
            "conversation_id": str(conversation_id),
            "user": {"id": str(user_id)},
            "env_slug": conv.env_slug or "default",
            "base_branch": base_branch,
            "cursor": cursor,  # passed through to pipe() for SSE resumption
        }

        return self._stream_chunks(
            injected_prompt, model_id, messages_payload, pipeline_body, conversation_id
        )

    async def _inject_diff_comments(
        self, conversation_id: uuid.UUID, content: str
    ) -> str:
        """Fetch unbundled diff_comments and prepend them to the prompt.

        After fetching, marks them as bundled so they are not injected again.
        Returns the augmented prompt string.
        """
        try:
            from sqlalchemy import text

            from app.infrastructure.database import async_session_factory

            async with async_session_factory() as session:
                rows = await session.execute(
                    text(
                        "SELECT id, file_path, line, content FROM diff_comments "
                        "WHERE conversation_id = :cid AND bundled_at IS NULL "
                        "ORDER BY file_path, line"
                    ),
                    {"cid": str(conversation_id)},
                )
                comments = rows.fetchall()
                if not comments:
                    return content

                lines = []
                for row in comments:
                    lines.append(f"at `{row.file_path}:{row.line}`: {row.content}")

                ids = [str(row.id) for row in comments]
                id_list = ", ".join(f"'{i}'" for i in ids)
                await session.execute(
                    text(
                        f"UPDATE diff_comments SET bundled_at = NOW() WHERE id IN ({id_list})"
                    )
                )
                await session.commit()

                injected = "\n".join(lines) + "\n\n" + content
                return injected
        except Exception:
            # Never block the message if diff_comments injection fails
            return content

    async def _stream_chunks(
        self,
        content: str,
        model_id: str,
        messages_payload: list[dict],
        pipeline_body: dict,
        conversation_id: uuid.UUID,
    ) -> AsyncGenerator[bytes, None]:
        accumulated_text: list[str] = []
        accumulated_error: list[str] = []
        gen = self._agent.pipe(content, model_id, messages_payload, pipeline_body)

        while True:
            chunk = await asyncio.to_thread(_next_chunk, gen)
            if chunk is None:
                break
            line = chunk.strip()
            if line.startswith("data: "):
                try:
                    evt = json.loads(line[6:])
                    if evt.get("type") == "text":
                        accumulated_text.append(evt.get("content", ""))
                    elif evt.get("type") == "error":
                        accumulated_error.append(evt.get("message", ""))
                except Exception:
                    pass
            yield chunk.encode("utf-8")

        assistant_text = "".join(accumulated_text).strip()
        if assistant_text:
            await self._messages.save(
                Message(
                    id=uuid.uuid4(),
                    conversation_id=conversation_id,
                    role="assistant",
                    content=assistant_text,
                )
            )
        elif accumulated_error:
            error_content = "**Erro:** " + " ".join(accumulated_error)
            await self._messages.save(
                Message(
                    id=uuid.uuid4(),
                    conversation_id=conversation_id,
                    role="assistant",
                    content=error_content,
                )
            )

