"""Schemas Pydantic para anexos (visão computacional).

Mantido em módulo separado para respeitar o limite de 300 linhas por arquivo
imposto pelo hook ``max-file-length``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class AttachmentOut(BaseModel):
    """Metadados de um anexo persistido associado a uma conversa.

    ``preview_url`` é construído pelo router HTTP e aponta para o endpoint
    autenticado ``GET /api/conversations/{cid}/attachments/{aid}``.
    """

    id: uuid.UUID
    conversation_id: uuid.UUID
    mime_type: str
    original_filename: str
    size_bytes: int
    kind: str = "image"
    has_description: bool = False
    processing_status: str = "uploaded"
    chunks_count: int = 0
    processing_error: str | None = None
    vision_model_used: str | None = None
    uploaded_at: datetime
    preview_url: str
