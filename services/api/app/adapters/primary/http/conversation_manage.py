"""Renomear e arquivar conversas.

  PATCH /conversations/{id}   {title?, archived?}   → só o dono da conversa

Arquivar não apaga nada (mensagens, worktree, branch): a conversa só sai da
lista padrão. ``GET /conversations?archived=true`` lista as arquivadas.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.adapters.primary.http.deps import get_authenticated_user, get_conv_repo
from app.application.use_cases._conversation_manage import (
    ConversationNotFoundError,
    InvalidConversationTitleError,
    UpdateConversation,
)
from app.domain.entities import User
from app.ports.repositories import ConversationRepository
from app.schemas import ConversationOut, ConversationPatch

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.patch("/{conversation_id}", response_model=ConversationOut)
async def update_conversation(
    conversation_id: uuid.UUID,
    body: ConversationPatch,
    current: Annotated[User, Depends(get_authenticated_user)],
    repo: Annotated[ConversationRepository, Depends(get_conv_repo)],
) -> ConversationOut:
    try:
        conv = await UpdateConversation(repo).execute(
            conversation_id, current.id, title=body.title, archived=body.archived
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada."
        ) from exc
    except InvalidConversationTitleError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ConversationOut.model_validate(conv.__dict__)
