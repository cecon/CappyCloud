"""Fakes em memória para anexos (visão computacional) usados nos testes.

Mantém ``conftest.py`` abaixo de 300 linhas (regra ``max-file-length``).
"""

from __future__ import annotations

import uuid

from app.domain.entities import ConversationArtifactChunk, MessageAttachment
from app.ports.repositories import AiModelCapabilityLookup, AttachmentRepository
from app.ports.services import AttachmentStorage, VisionDescriber


class InMemoryAttachmentRepository(AttachmentRepository):
    """In-memory attachment metadata store for testing."""

    def __init__(self) -> None:
        self._store: dict[uuid.UUID, MessageAttachment] = {}
        self._chunks: dict[uuid.UUID, list[ConversationArtifactChunk]] = {}

    async def save(self, attachment: MessageAttachment) -> MessageAttachment:
        self._store[attachment.id] = attachment
        return attachment

    async def get(
        self, attachment_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> MessageAttachment | None:
        att = self._store.get(attachment_id)
        if att and att.conversation_id == conversation_id:
            return att
        return None

    async def list_by_ids(
        self, attachment_ids: list[uuid.UUID], conversation_id: uuid.UUID
    ) -> list[MessageAttachment]:
        ids = set(attachment_ids)
        rows = [
            a for a in self._store.values() if a.id in ids and a.conversation_id == conversation_id
        ]
        return sorted(rows, key=lambda a: a.uploaded_at)

    async def delete(self, attachment_id: uuid.UUID, conversation_id: uuid.UUID) -> bool:
        att = self._store.get(attachment_id)
        if att and att.conversation_id == conversation_id:
            del self._store[attachment_id]
            return True
        return False

    async def update_description(
        self,
        attachment_id: uuid.UUID,
        description: str,
        model_used: str,
    ) -> None:
        att = self._store.get(attachment_id)
        if att:
            att.vision_description = description
            att.vision_model_used = model_used

    async def update_processing(
        self,
        attachment_id: uuid.UUID,
        *,
        status: str,
        chunks_count: int = 0,
        error: str | None = None,
    ) -> None:
        att = self._store.get(attachment_id)
        if att:
            att.processing_status = status
            att.chunks_count = chunks_count
            att.processing_error = error

    async def save_chunks(self, chunks: list[ConversationArtifactChunk]) -> None:
        for chunk in chunks:
            self._chunks.setdefault(chunk.attachment_id, []).append(chunk)

    async def search_chunks(
        self,
        *,
        conversation_id: uuid.UUID,
        attachment_ids: list[uuid.UUID],
        query: str,
        limit: int,
    ) -> list[ConversationArtifactChunk]:
        terms = [term.lower() for term in query.split() if len(term) >= 3][:8]
        rows: list[ConversationArtifactChunk] = []
        for attachment_id in attachment_ids:
            rows.extend(self._chunks.get(attachment_id, []))
        rows = [row for row in rows if row.conversation_id == conversation_id]
        if terms:
            matched = [row for row in rows if any(term in row.content.lower() for term in terms)]
            rows = matched or rows
        return sorted(rows, key=lambda row: (str(row.attachment_id), row.chunk_index))[:limit]


class InMemoryAttachmentStorage(AttachmentStorage):
    """In-memory binary store keyed by synthetic path."""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    async def save(self, *, conversation_id: str, filename: str, content: bytes) -> str:
        path = f"mem://{conversation_id}/{uuid.uuid4().hex}-{filename}"
        self._store[path] = content
        return path

    async def read(self, storage_path: str) -> bytes:
        return self._store[storage_path]

    async def delete(self, storage_path: str) -> bool:
        return self._store.pop(storage_path, None) is not None


class FakeVisionDescriber(VisionDescriber):
    """Devolve uma descrição determinística baseada no tamanho dos bytes."""

    def __init__(
        self,
        *,
        description: str = "Descrição fake (teste)",
        model: str = "fake-vision-1",
    ) -> None:
        self._description = description
        self._model = model

    async def describe(
        self, *, mime_type: str, content: bytes, hint: str | None = None
    ) -> tuple[str, str]:
        suffix = f" [{len(content)}B {mime_type}]"
        return self._description + suffix, self._model


class InMemoryAiModelCapabilityLookup(AiModelCapabilityLookup):
    """Fake configurável: caller regista quais ``model_id`` são vision."""

    def __init__(self, vision_models: set[str] | None = None) -> None:
        self._vision = set(vision_models or set())

    async def is_vision_capable(self, model_id: str) -> bool:
        return model_id in self._vision

    def add_vision(self, model_id: str) -> None:
        """Técnica de teste: marca o modelo como vision-capable."""
        self._vision.add(model_id)
