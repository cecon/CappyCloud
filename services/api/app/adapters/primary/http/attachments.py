"""HTTP endpoints para anexos de conversas.

Rotas:
- ``POST   /api/conversations/{conv_id}/attachments``   (multipart/form-data: file)
- ``GET    /api/conversations/{conv_id}/attachments/{att_id}``  (preview)
- ``DELETE /api/conversations/{conv_id}/attachments/{att_id}``

A descrição textual gerada pelo vision describer é persistida durante o
upload — fica pronta para o ``StreamMessage`` injetar no prompt assim que o
utilizador clicar em "enviar".
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)

from app.adapters.primary.http.deps import get_authenticated_user
from app.adapters.primary.http.deps_attachments import (
    get_delete_attachment_uc,
    get_get_attachment_uc,
    get_upload_attachment_uc,
)
from app.application.use_cases.attachments import (
    AttachmentNotFoundError,
    DeleteAttachment,
    GetAttachmentBytes,
    UploadAttachment,
)
from app.domain.entities import User
from app.infrastructure.config import get_settings
from app.schemas import AttachmentOut

router = APIRouter(prefix="/api/conversations", tags=["attachments"])

_ALLOWED_MIME = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}


def _attachment_to_dto(att, conv_id: uuid.UUID) -> AttachmentOut:
    return AttachmentOut(
        id=att.id,
        conversation_id=conv_id,
        mime_type=att.mime_type,
        original_filename=att.original_filename,
        size_bytes=att.size_bytes,
        kind=att.kind,
        has_description=bool(att.vision_description),
        vision_model_used=att.vision_model_used,
        uploaded_at=att.uploaded_at,
        preview_url=f"/api/conversations/{conv_id}/attachments/{att.id}",
    )


@router.post(
    "/{conversation_id}/attachments",
    response_model=AttachmentOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    conversation_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[UploadAttachment, Depends(get_upload_attachment_uc)],
    file: Annotated[UploadFile, File(...)],
) -> AttachmentOut:
    """Faz upload de uma imagem e gera descrição via modelo de visão."""
    mime = (file.content_type or "").lower()
    if mime not in _ALLOWED_MIME:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(f"Tipo {mime!r} não suportado. Aceitos: " + ", ".join(_ALLOWED_MIME)),
        )
    settings = get_settings()
    content = await file.read()
    try:
        att = await uc.execute(
            conversation_id=conversation_id,
            user_id=current.id,
            original_filename=file.filename or "image",
            mime_type=mime,
            content=content,
            max_bytes=settings.attachments_max_bytes,
        )
    except AttachmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _attachment_to_dto(att, conversation_id)


@router.get("/{conversation_id}/attachments/{attachment_id}")
async def get_attachment(
    conversation_id: uuid.UUID,
    attachment_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[GetAttachmentBytes, Depends(get_get_attachment_uc)],
) -> Response:
    """Devolve o conteúdo binário do anexo (para preview/download)."""
    try:
        content, mime_type, filename = await uc.execute(
            attachment_id=attachment_id,
            conversation_id=conversation_id,
            user_id=current.id,
        )
    except AttachmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type=mime_type,
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.delete(
    "/{conversation_id}/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_attachment(
    conversation_id: uuid.UUID,
    attachment_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    uc: Annotated[DeleteAttachment, Depends(get_delete_attachment_uc)],
) -> Response:
    """Apaga o anexo (storage físico + registo no banco)."""
    try:
        await uc.execute(
            attachment_id=attachment_id,
            conversation_id=conversation_id,
            user_id=current.id,
        )
    except AttachmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
