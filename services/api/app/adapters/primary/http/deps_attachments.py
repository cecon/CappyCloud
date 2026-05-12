"""Dependências FastAPI específicas de anexos (visão computacional).

Extraídas de ``deps.py`` para manter o módulo principal abaixo de 300 linhas.
Cada provider devolve a porta abstracta — os adapters concretos vivem em
``app.adapters.secondary.{persistence,storage,vision}``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.secondary.persistence.sqlalchemy_ai_model_lookup import (
    SQLAlchemyAiModelCapabilityLookup,
)
from app.adapters.secondary.persistence.sqlalchemy_attachment_repo import (
    SQLAlchemyAttachmentRepository,
)
from app.adapters.secondary.storage.local_volume_attachment_storage import (
    LocalVolumeAttachmentStorage,
)
from app.adapters.secondary.vision.openrouter_vision_describer import (
    OpenRouterVisionDescriber,
)
from app.application.use_cases.attachments import (
    DeleteAttachment,
    GetAttachmentBytes,
    UploadAttachment,
)
from app.infrastructure.config import get_settings
from app.ports.repositories import (
    AiModelCapabilityLookup,
    AttachmentRepository,
    ConversationRepository,
)
from app.ports.services import AttachmentStorage, VisionDescriber

from .deps_base import get_conv_repo, get_db_session

# get_db_session é usado nas assinaturas via Depends() em get_attachment_repo;
# o re-export silencia "imported but unused".
_ = get_db_session


def get_attachment_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AttachmentRepository:
    return SQLAlchemyAttachmentRepository(session)


def get_ai_model_caps(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AiModelCapabilityLookup:
    return SQLAlchemyAiModelCapabilityLookup(session)


def get_attachment_storage() -> AttachmentStorage:
    settings = get_settings()
    return LocalVolumeAttachmentStorage(base_dir=settings.attachments_dir)


def get_vision_describer() -> VisionDescriber:
    settings = get_settings()
    return OpenRouterVisionDescriber(
        api_key=settings.vision_provider_api_key,
        base_url=settings.vision_provider_base_url,
        model=settings.vision_model,
        max_tokens=settings.vision_max_tokens,
        timeout_s=settings.vision_timeout_s,
    )


def get_upload_attachment_uc(
    convs: Annotated[ConversationRepository, Depends(get_conv_repo)],
    attachments: Annotated[AttachmentRepository, Depends(get_attachment_repo)],
    storage: Annotated[AttachmentStorage, Depends(get_attachment_storage)],
    vision: Annotated[VisionDescriber, Depends(get_vision_describer)],
) -> UploadAttachment:
    return UploadAttachment(
        conversations=convs,
        attachments=attachments,
        storage=storage,
        vision=vision,
    )


def get_get_attachment_uc(
    convs: Annotated[ConversationRepository, Depends(get_conv_repo)],
    attachments: Annotated[AttachmentRepository, Depends(get_attachment_repo)],
    storage: Annotated[AttachmentStorage, Depends(get_attachment_storage)],
) -> GetAttachmentBytes:
    return GetAttachmentBytes(
        conversations=convs,
        attachments=attachments,
        storage=storage,
    )


def get_delete_attachment_uc(
    convs: Annotated[ConversationRepository, Depends(get_conv_repo)],
    attachments: Annotated[AttachmentRepository, Depends(get_attachment_repo)],
    storage: Annotated[AttachmentStorage, Depends(get_attachment_storage)],
) -> DeleteAttachment:
    return DeleteAttachment(
        conversations=convs,
        attachments=attachments,
        storage=storage,
    )
