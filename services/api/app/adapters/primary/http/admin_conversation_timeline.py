"""Admin: o que o usuário viu na conversa além do texto (só leitura).

  GET /admin/conversations/{id}/activity                 → passos do agente por turno
  GET /admin/conversations/{id}/attachments              → anexos, cada um na pergunta dele
  GET /admin/conversations/{id}/attachments/{att_id}     → arquivo do anexo

Mesma guarda das outras rotas de conversas do admin: ADMIN global vê tudo,
admin de workspace só as conversas dos workspaces que administra.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.conversation_activity import load_conversation_activity
from app.adapters.primary.http.deps import get_db_session
from app.adapters.primary.http.deps_attachments import get_attachment_storage
from app.adapters.primary.http.deps_auth import get_admin_scope
from app.application.use_cases.admin_scope import AdminScope
from app.infrastructure.orm_models import Conversation, Message, MessageAttachment
from app.ports.services import AttachmentStorage

router = APIRouter(prefix="/admin/conversations", tags=["admin"])

Session = Annotated[AsyncSession, Depends(get_db_session)]
Scope = Annotated[AdminScope, Depends(get_admin_scope)]
Storage = Annotated[AttachmentStorage, Depends(get_attachment_storage)]


class AdminAttachment(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    # Pergunta do usuário em que o anexo foi enviado (None se a conversa não tem perguntas).
    message_id: uuid.UUID | None
    mime_type: str
    original_filename: str
    size_bytes: int
    kind: str
    has_description: bool
    processing_status: str
    chunks_count: int
    processing_error: str | None
    vision_model_used: str | None
    uploaded_at: datetime
    preview_url: str


async def _conversation_in_scope(
    session: AsyncSession, scope: AdminScope, conversation_id: uuid.UUID
) -> None:
    found = (
        await session.execute(
            select(Conversation.workspace_id).where(Conversation.id == conversation_id)
        )
    ).first()
    if found is None:
        raise HTTPException(status_code=404, detail="Conversa não encontrada.")
    if not scope.allows(found.workspace_id):
        raise HTTPException(status_code=403, detail="Você não administra este workspace.")


def assign_attachments_to_messages(
    uploads: list[tuple[uuid.UUID | None, datetime]],
    questions: list[tuple[uuid.UUID, datetime]],
) -> list[uuid.UUID | None]:
    """Pergunta de cada anexo: a gravada no anexo ou a primeira enviada depois do upload.

    O envio não grava ``message_id`` no anexo; o upload acontece antes de a
    pergunta ser salva, então a dona é a primeira pergunta com ``created_at``
    igual ou posterior ao upload. Sem pergunta depois, fica na última.
    """
    owners: list[uuid.UUID | None] = []
    for message_id, uploaded_at in uploads:
        if message_id is not None:
            owners.append(message_id)
            continue
        after = next((qid for qid, at in questions if _naive(at) >= _naive(uploaded_at)), None)
        owners.append(after or (questions[-1][0] if questions else None))
    return owners


def _naive(value: datetime) -> datetime:
    # SQLite devolve datas sem fuso; Postgres com fuso. Comparar sempre sem.
    return value.replace(tzinfo=None) if value.tzinfo else value


@router.get("/{conversation_id}/activity")
async def get_conversation_activity(
    conversation_id: uuid.UUID, session: Session, scope: Scope
) -> list[dict]:
    await _conversation_in_scope(session, scope, conversation_id)
    return await load_conversation_activity(session, conversation_id)


@router.get("/{conversation_id}/attachments", response_model=list[AdminAttachment])
async def list_attachments(
    conversation_id: uuid.UUID, session: Session, scope: Scope
) -> list[AdminAttachment]:
    await _conversation_in_scope(session, scope, conversation_id)
    attachments = (
        (
            await session.execute(
                select(MessageAttachment)
                .where(MessageAttachment.conversation_id == conversation_id)
                .order_by(MessageAttachment.uploaded_at)
            )
        )
        .scalars()
        .all()
    )
    questions = (
        await session.execute(
            select(Message.id, Message.created_at)
            .where(Message.conversation_id == conversation_id, Message.role == "user")
            .order_by(Message.created_at)
        )
    ).all()
    owners = assign_attachments_to_messages(
        [(a.message_id, a.uploaded_at) for a in attachments],
        [(q.id, q.created_at) for q in questions],
    )
    return [
        AdminAttachment(
            id=a.id,
            conversation_id=conversation_id,
            message_id=owner,
            mime_type=a.mime_type,
            original_filename=a.original_filename,
            size_bytes=a.size_bytes,
            kind=a.kind,
            has_description=bool(a.vision_description),
            processing_status=a.processing_status,
            chunks_count=a.chunks_count,
            processing_error=a.processing_error,
            vision_model_used=a.vision_model_used,
            uploaded_at=a.uploaded_at,
            preview_url=f"/api/admin/conversations/{conversation_id}/attachments/{a.id}",
        )
        for a, owner in zip(attachments, owners, strict=True)
    ]


@router.get("/{conversation_id}/attachments/{attachment_id}")
async def get_attachment(
    conversation_id: uuid.UUID,
    attachment_id: uuid.UUID,
    session: Session,
    scope: Scope,
    storage: Storage,
) -> Response:
    await _conversation_in_scope(session, scope, conversation_id)
    attachment = await session.scalar(
        select(MessageAttachment).where(
            MessageAttachment.id == attachment_id,
            MessageAttachment.conversation_id == conversation_id,
        )
    )
    if attachment is None:
        raise HTTPException(status_code=404, detail="Anexo não encontrado.")
    try:
        content = await storage.read(attachment.storage_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Arquivo do anexo não existe mais.") from exc
    # filename* aceita acentos; cabeçalho HTTP cru só aceita latin-1.
    filename = quote(attachment.original_filename)
    return Response(
        content=content,
        media_type=attachment.mime_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{filename}",
            "Cache-Control": "private, max-age=3600",
        },
    )
