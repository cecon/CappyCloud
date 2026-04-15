"""Conversation use cases — business logic for chat management and agent streaming.

No FastAPI, no SQLAlchemy. All dependencies injected via ports (ABCs).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator

from app.domain.entities import Conversation, Message
from app.ports.agent import AgentPort
from app.ports.repositories import ConversationRepository, MessageRepository

_TITLE_MAX_LEN = 80
_DEFAULT_TITLE = "Nova conversa"


def _next_chunk(gen):  # type: ignore[no-untyped-def]
    """Pull one chunk from a synchronous generator (for asyncio.to_thread)."""
    try:
        return next(gen)
    except StopIteration:
        return None


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
        self, user_id: uuid.UUID, title: str | None = None
    ) -> Conversation:
        conv = Conversation(
            id=uuid.uuid4(),
            user_id=user_id,
            title=title or _DEFAULT_TITLE,
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

    async def execute(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[Message]:
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
    2. Persist the user message.
    3. Optionally auto-title the conversation.
    4. Load history and call the agent.
    5. Yield SSE bytes to the HTTP layer.
    6. Persist the accumulated assistant response after streaming.

    Usage::

        stream = await use_case.execute(conv_id, user_id, content)
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
    ) -> AsyncGenerator[bytes, None]:
        """Validate ownership, persist user msg, return streaming async generator.

        Raises:
            LookupError: if conversation not found or not owned by user.
        """
        conv = await self._conversations.get(conversation_id, user_id)
        if not conv:
            raise LookupError("Conversa não encontrada.")

        await self._messages.save(
            Message(
                id=uuid.uuid4(),
                conversation_id=conv.id,
                role="user",
                content=content,
            )
        )

        if conv.title == _DEFAULT_TITLE:
            conv.title = content[:_TITLE_MAX_LEN] + (
                "…" if len(content) > _TITLE_MAX_LEN else ""
            )
            await self._conversations.update(conv)

        history = await self._messages.list_by_conversation(conversation_id)
        messages_payload = [{"role": m.role, "content": m.content} for m in history]
        pipeline_body = {
            "user_id": str(user_id),
            "conversation_id": str(conversation_id),
            "user": {"id": str(user_id)},
        }

        # Return the async generator (not awaited — calling it creates the generator object)
        return self._stream_chunks(
            content, model_id, messages_payload, pipeline_body, conversation_id
        )

    async def _stream_chunks(
        self,
        content: str,
        model_id: str,
        messages_payload: list[dict],  # type: ignore[type-arg]
        pipeline_body: dict,  # type: ignore[type-arg]
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
