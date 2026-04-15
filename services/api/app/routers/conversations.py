"""Conversas e mensagens com streaming do agente."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, get_db
from app.deps import get_current_user
from app.models import Conversation, Message, User
from app.schemas import ConversationCreate, ConversationOut, MessageOut, SendMessageBody

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _next_chunk(gen):
    try:
        return next(gen)
    except StopIteration:
        return None


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
) -> list[Conversation]:
    """Lista conversas do utilizador."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current.id)
        .order_by(Conversation.updated_at.desc())
    )
    return list(result.scalars().all())


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
    body: ConversationCreate | None = None,
) -> Conversation:
    """Cria conversa nova."""
    title = "Nova conversa"
    if body and body.title:
        title = body.title
    conv = Conversation(user_id=current.id, title=title)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
async def list_messages(
    conversation_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
) -> list[Message]:
    """Histórico de mensagens."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current.id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    r2 = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    return list(r2.scalars().all())


@router.post("/{conversation_id}/messages/stream")
async def stream_message(
    request: Request,
    conversation_id: uuid.UUID,
    body: SendMessageBody,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse:
    """
    Envia mensagem do utilizador e devolve a resposta do agente em UTF-8 chunked.

    O cliente pode usar fetch() com ReadableStream.
    """
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")

    user_msg = Message(conversation_id=conv.id, role="user", content=body.content)
    db.add(user_msg)
    if conv.title == "Nova conversa":
        conv.title = body.content[:80] + ("…" if len(body.content) > 80 else "")
    await db.commit()

    r_msgs = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    messages_rows = list(r_msgs.scalars().all())
    messages_payload = [{"role": m.role, "content": m.content} for m in messages_rows]

    pipeline_body = {
        "user_id": str(current.id),
        "conversation_id": str(conversation_id),
        "user": {"id": str(current.id)},
    }

    pipeline = request.app.state.pipeline

    async def body_iter():
        accumulated_text: list[str] = []

        gen = pipeline.pipe(
            body.content,
            "cappycloud",
            messages_payload,
            pipeline_body,
        )
        while True:
            chunk = await asyncio.to_thread(_next_chunk, gen)
            if chunk is None:
                break
            # Extract only text content for DB storage
            line = chunk.strip()
            if line.startswith("data: "):
                try:
                    evt = json.loads(line[6:])
                    if evt.get("type") == "text":
                        accumulated_text.append(evt.get("content", ""))
                except Exception:
                    pass
            yield chunk.encode("utf-8")

        assistant_text = "".join(accumulated_text).strip()
        if assistant_text:
            async with async_session_factory() as s2:
                s2.add(
                    Message(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=assistant_text,
                    )
                )
                await s2.commit()

    return StreamingResponse(
        body_iter(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
