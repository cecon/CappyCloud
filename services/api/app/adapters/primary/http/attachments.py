"""HTTP endpoints para anexos/artefatos de conversas.

Rotas:
- ``POST   /api/conversations/{conv_id}/attachments``   (multipart/form-data: file)
- ``GET    /api/conversations/{conv_id}/attachments/{att_id}``  (preview)
- ``DELETE /api/conversations/{conv_id}/attachments/{att_id}``

Imagens recebem descrição via vision. Arquivos textuais/documentos são extraídos
e indexados em chunks no escopo da conversa para busca no turno do agente.
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


def _attachment_to_dto(att, conv_id: uuid.UUID) -> AttachmentOut:
    return AttachmentOut(
        id=att.id,
        conversation_id=conv_id,
        mime_type=att.mime_type,
        original_filename=att.original_filename,
        size_bytes=att.size_bytes,
        kind=att.kind,
        has_description=bool(att.vision_description),
        processing_status=att.processing_status,
        chunks_count=att.chunks_count,
        processing_error=att.processing_error,
        vision_model_used=att.vision_model_used,
        uploaded_at=att.uploaded_at,
        preview_url=f"/api/conversations/{conv_id}/attachments/{att.id}",
    )


def _status_for_upload_error(message: str) -> int:
    lowered = message.lower()
    if "acima do limite" in lowered:
        return status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    if "tipo de arquivo" in lowered or "não são suportados" in lowered:
        return status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    return status.HTTP_400_BAD_REQUEST


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
    """Faz upload de uma imagem ou artefato pesquisável da conversa."""
    mime = (file.content_type or "application/octet-stream").lower()
    settings = get_settings()
    content = await file.read()
    try:
        att = await uc.execute(
            conversation_id=conversation_id,
            user_id=current.id,
            original_filename=file.filename or "image",
            mime_type=mime,
            content=content,
            max_bytes=settings.conversation_artifacts_max_bytes,
            image_max_bytes=settings.attachments_max_bytes,
        )
    except AttachmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=_status_for_upload_error(str(exc)),
            detail=str(exc),
        ) from exc
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
