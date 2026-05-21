"""Conversation CRUD/list use cases."""

from __future__ import annotations

import uuid

from app.application.use_cases._conversation_titles import DEFAULT_TITLE
from app.domain.entities import Conversation, Message
from app.ports.repositories import (
    ConversationRepository,
    MessageRepository,
    RepositoryRepository,
)


class ListConversations:
    def __init__(self, conversations: ConversationRepository) -> None:
        self._conversations = conversations

    async def execute(self, user_id: uuid.UUID) -> list[Conversation]:
        return await self._conversations.list_by_user(user_id)


class CreateConversation:
    def __init__(
        self,
        conversations: ConversationRepository,
        repositories: RepositoryRepository | None = None,
    ) -> None:
        self._conversations = conversations
        self._repositories = repositories

    async def execute(
        self,
        user_id: uuid.UUID,
        title: str | None = None,
        sandbox_id: uuid.UUID | None = None,
        repos: list[dict] | None = None,
    ) -> Conversation:
        conv_id = uuid.uuid4()
        short_id = conv_id.hex[:12]
        resolved_repos: list[dict] = []
        for r in repos or []:
            slug = r["slug"]
            alias = r.get("alias") or slug
            repo_entity = await self._repositories.get_by_slug(slug) if self._repositories else None
            resolved_repos.append(
                {
                    "slug": slug,
                    "alias": alias,
                    "base_branch": r.get("base_branch") or "main",
                    "branch_name": f"cappy/{slug}/{short_id}-{alias}",
                    "worktree_path": f"/repos/sessions/{short_id}/{alias}",
                    "repo_id": str(repo_entity.id) if repo_entity else None,
                    "sandbox_id": str(repo_entity.sandbox_id)
                    if repo_entity and repo_entity.sandbox_id
                    else None,
                    "confluence_url": repo_entity.confluence_url if repo_entity else "",
                    "confluence_space": repo_entity.confluence_space if repo_entity else "",
                    "confluence_labels": list(repo_entity.confluence_labels) if repo_entity else [],
                }
            )

        conv = Conversation(
            id=conv_id,
            user_id=user_id,
            title=title or DEFAULT_TITLE,
            sandbox_id=sandbox_id,
            repos=resolved_repos,
            session_root=f"/repos/sessions/{short_id}",
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
