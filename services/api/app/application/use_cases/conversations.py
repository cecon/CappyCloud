"""Conversation and messaging use cases — business logic for chat management."""

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
    try:
        return next(gen)
    except StopIteration:
        return None


# ── Conversation use cases ────────────────────────────────────


class ListConversations:
    def __init__(self, conversations: ConversationRepository) -> None:
        self._conversations = conversations

    async def execute(self, user_id: uuid.UUID) -> list[Conversation]:
        return await self._conversations.list_by_user(user_id)


class CreateConversation:
    """Create a new conversation, setting up multi-repo session metadata."""

    def __init__(self, conversations: ConversationRepository) -> None:
        self._conversations = conversations

    async def execute(
        self,
        user_id: uuid.UUID,
        title: str | None = None,
        sandbox_id: uuid.UUID | None = None,
        repos: list[dict] | None = None,
        agent_id: uuid.UUID | None = None,
    ) -> Conversation:
        conv_id = uuid.uuid4()
        short_id = conv_id.hex[:12]

        resolved_repos: list[dict] = []
        for r in repos or []:
            slug = r["slug"]
            alias = r.get("alias") or slug
            base = r.get("base_branch") or "main"
            branch_name = f"cappy/{slug}/{short_id}-{alias}"
            worktree_path = f"/repos/sessions/{short_id}/{alias}"
            resolved_repos.append(
                {
                    "slug": slug,
                    "alias": alias,
                    "base_branch": base,
                    "branch_name": branch_name,
                    "worktree_path": worktree_path,
                }
            )

        session_root = f"/repos/sessions/{short_id}"

        conv = Conversation(
            id=conv_id,
            user_id=user_id,
            title=title or _DEFAULT_TITLE,
            sandbox_id=sandbox_id,
            agent_id=agent_id,
            repos=resolved_repos,
            session_root=session_root,
        )
        return await self._conversations.save(conv)


class ListMessages:
    def __init__(
        self,
        conversations: ConversationRepository,
        messages: MessageRepository,
    ) -> None:
        self._conversations = conversations
        self._messages = messages

    async def execute(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> list[Message]:
        conv = await self._conversations.get(conversation_id, user_id)
        if not conv:
            raise LookupError("Conversa não encontrada.")
        return await self._messages.list_by_conversation(conversation_id)


class StreamMessage:
    """Orchestrate sending a user message and streaming the agent response."""

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
    ) -> AsyncGenerator[bytes]:
        conv = await self._conversations.get(conversation_id, user_id)
        if not conv:
            raise LookupError("Conversa não encontrada.")

        injected_prompt = await self._inject_diff_comments(conversation_id, content)

        await self._messages.save(
            Message(
                id=uuid.uuid4(),
                conversation_id=conv.id,
                role="user",
                content=content,
            )
        )

        if conv.title == _DEFAULT_TITLE:
            conv.title = content[:_TITLE_MAX_LEN] + ("…" if len(content) > _TITLE_MAX_LEN else "")
            await self._conversations.update(conv)

        history = await self._messages.list_by_conversation(conversation_id)
        messages_payload = [{"role": m.role, "content": m.content} for m in history]

        pipeline_body = self._build_pipeline_body(conv, user_id, cursor)

        return self._stream_chunks(
            injected_prompt, model_id, messages_payload, pipeline_body, conversation_id
        )

    def _build_pipeline_body(
        self,
        conv: Conversation,
        user_id: uuid.UUID,
        cursor: int | None,
    ) -> dict:
        return {
            "user_id": str(user_id),
            "conversation_id": str(conv.id),
            "user": {"id": str(user_id)},
            "cursor": cursor,
            "repos": conv.repos,
            "session_root": conv.session_root or "",
            "sandbox_id": str(conv.sandbox_id) if conv.sandbox_id else "",
            "agent_id": str(conv.agent_id) if conv.agent_id else "",
        }

    async def _inject_diff_comments(self, conversation_id: uuid.UUID, content: str) -> str:
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

                lines = [f"at `{row.file_path}:{row.line}`: {row.content}" for row in comments]
                ids = ", ".join(f"'{row.id}'" for row in comments)
                await session.execute(
                    text(f"UPDATE diff_comments SET bundled_at = NOW() WHERE id IN ({ids})")
                )
                await session.commit()
                return "\n".join(lines) + "\n\n" + content
        except Exception:
            return content

    async def _stream_chunks(
        self,
        content: str,
        model_id: str,
        messages_payload: list[dict],
        pipeline_body: dict,
        conversation_id: uuid.UUID,
    ) -> AsyncGenerator[bytes]:
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
            await self._messages.save(
                Message(
                    id=uuid.uuid4(),
                    conversation_id=conversation_id,
                    role="assistant",
                    content="**Erro:** " + " ".join(accumulated_error),
                )
            )
