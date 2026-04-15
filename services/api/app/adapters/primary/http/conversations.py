"""HTTP adapter for conversation and messaging endpoints — thin glue only."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.adapters.primary.http.deps import (
    get_authenticated_user,
    get_create_conv_uc,
    get_list_convs_uc,
    get_list_msgs_uc,
    get_stream_msg_uc,
)
from app.application.use_cases.conversations import (
    CreateConversation,
    ListConversations,
    ListMessages,
    StreamMessage,
)
from app.domain.entities import User
from app.schemas import ConversationCreate, ConversationOut, MessageOut, SendMessageBody

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[ListConversations, Depends(get_list_convs_uc)],
) -> list[ConversationOut]:
    """Lista conversas do utilizador."""
    convs = await uc.execute(current.id)
    return [
        ConversationOut(
            id=c.id,
            title=c.title,
            created_at=c.created_at,
            updated_at=c.updated_at,
            environment_id=c.environment_id,
            env_slug=c.env_slug,
        )
        for c in convs
    ]


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[CreateConversation, Depends(get_create_conv_uc)],
    body: ConversationCreate | None = None,
) -> ConversationOut:
    """Cria conversa nova, opcionalmente ligada a um ambiente."""
    title = body.title if body and body.title else None
    environment_id = body.environment_id if body else None
    base_branch = body.base_branch if body else None
    conv = await uc.execute(current.id, title, environment_id, base_branch)
    return ConversationOut(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        environment_id=conv.environment_id,
        env_slug=conv.env_slug,
        base_branch=conv.base_branch,
    )


@router.get(
    "/{conversation_id}/messages",
    response_model=list[MessageOut],
)
async def list_messages(
    conversation_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[ListMessages, Depends(get_list_msgs_uc)],
) -> list[MessageOut]:
    """Histórico de mensagens."""
    try:
        msgs = await uc.execute(conversation_id, current.id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [
        MessageOut(id=m.id, role=m.role, content=m.content, created_at=m.created_at)
        for m in msgs
    ]


@router.post("/{conversation_id}/messages/stream")
async def stream_message(
    conversation_id: uuid.UUID,
    body: SendMessageBody,
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[StreamMessage, Depends(get_stream_msg_uc)],
) -> StreamingResponse:
    """Envia mensagem e devolve resposta do agente em SSE chunks."""
    try:
        stream = await uc.execute(conversation_id, current.id, body.content)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
