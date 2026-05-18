"""Use cases para anexos (upload, descrição, listagem, remoção)."""

from __future__ import annotations

import uuid

from app.application.use_cases.artifact_processing import (
    ArtifactProcessingError,
    detect_artifact_kind,
    process_artifact,
)
from app.domain.entities import MessageAttachment
from app.ports.repositories import (
    AttachmentRepository,
    ConversationRepository,
)
from app.ports.services import AttachmentStorage, VisionDescriber


class AttachmentNotFoundError(LookupError):
    """Anexo não existe ou não pertence à conversa/utilizador."""


class UploadAttachment:
    """Persiste o ficheiro, regista metadado e dispara descrição via visão.

    A descrição roda **inline** (até ~8s) para que o frontend possa mostrar
    feedback imediato no preview do anexo. Em caso de erro/timeout, o anexo
    fica no banco com ``vision_description=None`` e o agente é avisado disso
    no prompt.
    """

    def __init__(
        self,
        *,
        conversations: ConversationRepository,
        attachments: AttachmentRepository,
        storage: AttachmentStorage,
        vision: VisionDescriber,
    ) -> None:
        self._conversations = conversations
        self._attachments = attachments
        self._storage = storage
        self._vision = vision

    async def execute(
        self,
        *,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        original_filename: str,
        mime_type: str,
        content: bytes,
        max_bytes: int,
        image_max_bytes: int,
    ) -> MessageAttachment:
        kind = detect_artifact_kind(original_filename, mime_type)
        if len(content) == 0:
            raise ValueError("Ficheiro vazio.")
        effective_max = image_max_bytes if kind == "image" else max_bytes
        if len(content) > effective_max:
            raise ValueError(
                f"Ficheiro acima do limite ({effective_max} bytes). "
                f"Tamanho recebido: {len(content)} bytes."
            )

        conv = await self._conversations.get(conversation_id, user_id)
        if not conv:
            raise AttachmentNotFoundError("Conversa não encontrada.")

        attachment_id = uuid.uuid4()
        chunks = []
        if kind != "image":
            try:
                processed = process_artifact(
                    attachment_id=attachment_id,
                    conversation_id=conversation_id,
                    filename=original_filename,
                    mime_type=mime_type,
                    content=content,
                )
            except ArtifactProcessingError as exc:
                raise ValueError(str(exc)) from exc
            chunks = processed.chunks

        storage_path = await self._storage.save(
            conversation_id=str(conversation_id),
            filename=original_filename,
            content=content,
        )

        attach = await self._attachments.save(
            MessageAttachment(
                id=attachment_id,
                conversation_id=conversation_id,
                mime_type=mime_type,
                storage_path=storage_path,
                original_filename=original_filename,
                size_bytes=len(content),
                kind=kind,
                processing_status="uploaded" if kind == "image" else "indexed",
                chunks_count=len(chunks),
                uploaded_by=user_id,
            )
        )

        if kind != "image":
            await self._attachments.save_chunks(chunks)
            return attach

        # Descrição via visão (síncrona). Se falhar, o método já devolve um
        # texto-fallback; persistimos na mesma para manter o histórico
        # auditável (incluindo o modelo tentado).
        description, model_used = await self._vision.describe(
            mime_type=mime_type,
            content=content,
            hint=f"Imagem anexada na conversa '{conv.title}'.",
        )
        await self._attachments.update_description(attach.id, description, model_used)
        await self._attachments.update_processing(
            attach.id, status="described", chunks_count=0, error=None
        )
        attach.vision_description = description
        attach.vision_model_used = model_used
        attach.processing_status = "described"
        return attach


class DeleteAttachment:
    """Apaga o anexo do storage físico e do banco."""

    def __init__(
        self,
        *,
        conversations: ConversationRepository,
        attachments: AttachmentRepository,
        storage: AttachmentStorage,
    ) -> None:
        self._conversations = conversations
        self._attachments = attachments
        self._storage = storage

    async def execute(
        self,
        *,
        attachment_id: uuid.UUID,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        conv = await self._conversations.get(conversation_id, user_id)
        if not conv:
            raise AttachmentNotFoundError("Conversa não encontrada.")
        att = await self._attachments.get(attachment_id, conversation_id)
        if not att:
            raise AttachmentNotFoundError("Anexo não encontrado.")
        await self._storage.delete(att.storage_path)
        await self._attachments.delete(attachment_id, conversation_id)


class GetAttachmentBytes:
    """Devolve bytes + mime para servir preview/download."""

    def __init__(
        self,
        *,
        conversations: ConversationRepository,
        attachments: AttachmentRepository,
        storage: AttachmentStorage,
    ) -> None:
        self._conversations = conversations
        self._attachments = attachments
        self._storage = storage

    async def execute(
        self,
        *,
        attachment_id: uuid.UUID,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> tuple[bytes, str, str]:
        conv = await self._conversations.get(conversation_id, user_id)
        if not conv:
            raise AttachmentNotFoundError("Conversa não encontrada.")
        att = await self._attachments.get(attachment_id, conversation_id)
        if not att:
            raise AttachmentNotFoundError("Anexo não encontrado.")
        content = await self._storage.read(att.storage_path)
        return content, att.mime_type, att.original_filename
