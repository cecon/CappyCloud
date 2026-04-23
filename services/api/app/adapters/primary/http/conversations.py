"""HTTP adapter for conversation and messaging endpoints — thin glue only."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
            sandbox_id=c.sandbox_id,
            agent_id=c.agent_id,
            repos=c.repos,
            session_root=c.session_root,
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
    b = body or ConversationCreate()
    repos_dicts = [r.model_dump() for r in b.repos] if b.repos else []
    conv = await uc.execute(
        current.id,
        title=b.title,
        sandbox_id=b.sandbox_id,
        repos=repos_dicts,
        agent_id=b.agent_id,
    )
    return ConversationOut(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        sandbox_id=conv.sandbox_id,
        agent_id=conv.agent_id,
        repos=conv.repos,
        session_root=conv.session_root,
    )


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
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
        MessageOut(id=m.id, role=m.role, content=m.content, created_at=m.created_at) for m in msgs
    ]


@router.post("/{conversation_id}/messages/stream")
async def stream_message(
    conversation_id: uuid.UUID,
    body: SendMessageBody,
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[StreamMessage, Depends(get_stream_msg_uc)],
    cursor: int | None = Query(
        default=None,
        description="Último agent_event.id recebido (para reconexão)",
    ),
) -> StreamingResponse:
    """Envia mensagem e devolve resposta do agente em SSE.

    Suporta reconexão via `cursor`: ao passar o último `agent_event.id` recebido,
    o stream retoma a partir desse ponto sem perder eventos.
    """
    try:
        stream = await uc.execute(conversation_id, current.id, body.content, cursor=cursor)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
