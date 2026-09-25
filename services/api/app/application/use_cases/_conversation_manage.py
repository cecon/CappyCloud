"""Renomear e arquivar conversas (só o dono da conversa)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.domain.entities import Conversation
from app.ports.repositories import ConversationRepository

TITLE_MAX_LEN = 200


class ConversationNotFoundError(Exception):
    """Conversa não existe ou não pertence ao usuário."""


class InvalidConversationTitleError(ValueError):
    """Título vazio depois de tirar os espaços."""


class UpdateConversation:
    def __init__(self, conversations: ConversationRepository) -> None:
        self._conversations = conversations

    async def execute(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        title: str | None = None,
        archived: bool | None = None,
    ) -> Conversation:
        conv = await self._conversations.get(conversation_id, user_id)
        if conv is None:
            raise ConversationNotFoundError(str(conversation_id))
        if title is not None:
            cleaned = " ".join(title.split())[:TITLE_MAX_LEN]
            if not cleaned:
                raise InvalidConversationTitleError("O título não pode ficar vazio.")
            conv.title = cleaned
        if archived is not None and archived != (conv.archived_at is not None):
            conv.archived_at = datetime.now(UTC) if archived else None
        return await self._conversations.update(conv)
