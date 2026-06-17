"""HTTP adapter for conversation and messaging endpoints — thin glue only."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import (
    get_authenticated_user,
    get_create_conv_uc,
    get_db_session,
    get_list_convs_uc,
    get_list_msgs_uc,
    get_stream_msg_uc,
)
from app.adapters.secondary.persistence.sqlalchemy_user_access_repo import (
    SQLAlchemyUserRepositoryAccessRepository,
    SQLAlchemyUserSandboxAccessRepository,
)
from app.application.use_cases.conversations import (
    CreateConversation,
    ListConversations,
    ListMessages,
    StreamMessage,
)
from app.domain.entities import User, UserRole
from app.infrastructure.orm_models import Repository
from app.schemas import (
    ConversationCreate,
    ConversationOut,
    ConversationUsage,
    MessageOut,
    PayloadSizeBreakdownOut,
    SendMessageBody,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[ListConversations, Depends(get_list_convs_uc)],
    scope: str = Query(default="own", pattern="^(own|all)$"),
) -> list[ConversationOut]:
    """Lista conversas do utilizador; ADMIN pode pedir ``scope=all``."""
    include_all = current.role is UserRole.ADMIN and scope == "all"
    convs = await uc.execute(current.id, include_all=include_all)
    return [
        ConversationOut(
            id=c.id,
            user_id=c.user_id if include_all else None,
            user_email=c.user_email if include_all else None,
            title=c.title,
            created_at=c.created_at,
            updated_at=c.updated_at,
            sandbox_id=c.sandbox_id,
            repos=c.repos,
            session_root=c.session_root,
        )
        for c in convs
    ]


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[CreateConversation, Depends(get_create_conv_uc)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    body: ConversationCreate | None = None,
) -> ConversationOut:
    """Cria conversa nova, opcionalmente ligada a um ambiente.

    USERs precisam ter ``UserSandboxAccess`` para o ``sandbox_id`` e
    ``UserRepositoryAccess`` para cada repositório listado em ``repos``
    (ADR-005 §5). ADMIN bypassa as duas validações.
    """
    b = body or ConversationCreate()

    if current.role is not UserRole.ADMIN:
        if b.sandbox_id is not None:
            ok = await SQLAlchemyUserSandboxAccessRepository(session).has_access(
                current.id, b.sandbox_id
            )
            if not ok:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Sem acesso à sandbox solicitada.",
                )
        if b.repos:
            slugs = [r.slug for r in b.repos]
            repo_rows = (
                (await session.execute(select(Repository).where(Repository.slug.in_(slugs))))
                .scalars()
                .all()
            )
            repo_ids = [r.id for r in repo_rows]
            if repo_ids:
                allowed = set(
                    await SQLAlchemyUserRepositoryAccessRepository(session).list_resources_for_user(
                        current.id
                    )
                )
                missing = [r for r in repo_rows if r.id not in allowed]
                if missing:
                    names = ", ".join(r.slug for r in missing)
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Sem acesso aos repositórios: {names}.",
                    )

    repos_dicts = [r.model_dump() for r in b.repos] if b.repos else []
    conv = await uc.execute(
        current.id,
        title=b.title,
        sandbox_id=b.sandbox_id,
        repos=repos_dicts,
    )
    return ConversationOut(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        sandbox_id=conv.sandbox_id,
        repos=conv.repos,
        session_root=conv.session_root,
    )


@router.get("/{conversation_id}/usage", response_model=ConversationUsage)
async def get_conversation_usage(
    conversation_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[ListMessages, Depends(get_list_msgs_uc)],
) -> ConversationUsage:
    """Totais agregados de tokens e custo da conversa.

    Soma todos os turnos do assistente (mensagens com ``role='assistant'``).
    """
    try:
        msgs = await uc.execute(conversation_id, current.id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ConversationUsage(
        total_prompt_tokens=sum(m.prompt_tokens for m in msgs),
        total_completion_tokens=sum(m.completion_tokens for m in msgs),
        total_cost_usd=round(sum(float(m.cost_usd) for m in msgs), 6),
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
        MessageOut(
            id=m.id,
            role=m.role,
            content=m.content,
            created_at=m.created_at,
            model_used=m.model_used,
            prompt_tokens=m.prompt_tokens,
            completion_tokens=m.completion_tokens,
            cost_usd=float(m.cost_usd),
            payload_diagnostics=(
                PayloadSizeBreakdownOut.model_validate(m.payload_diagnostics)
                if m.payload_diagnostics
                else None
            ),
        )
        for m in msgs
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
        stream = await uc.execute(
            conversation_id,
            current.id,
            body.content,
            user_role=current.role,
            cursor=cursor,
            override_model=body.model_id,
            attachment_ids=body.attachment_ids,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
