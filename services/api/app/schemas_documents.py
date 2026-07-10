"""Pydantic schemas para Documentos de referência (RAG por repositório)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# Tipos de fonte aceites na criação. ``text`` permite colar conteúdo direto.
_SOURCE_TYPES = {"pdf", "xlsx", "url", "text", "markdown", "txt", "docx"}


class DocumentCreate(BaseModel):
    """Cria um documento por URL ou texto colado.

    Para upload de arquivos (PDF/XLSX/Markdown/TXT/DOCX) usa o endpoint multipart dedicado.
    """

    source_type: str = Field(min_length=2, max_length=32)
    source_uri: str = Field(default="", max_length=2048)
    title: str | None = Field(default=None, max_length=512)
    content: str | None = Field(
        default=None,
        max_length=2_000_000,
        description="Texto bruto — obrigatório quando source_type='text'.",
    )

    def normalized_source_type(self) -> str:
        st = (self.source_type or "").strip().lower()
        if st not in _SOURCE_TYPES:
            raise ValueError(f"source_type inválido: {st!r}. Use um de {sorted(_SOURCE_TYPES)}.")
        return st


class DocumentOut(BaseModel):
    id: uuid.UUID
    repository_id: uuid.UUID
    source_type: str
    source_uri: str
    title: str
    version: int
    checksum: str | None = None
    status: str
    error_message: str | None = None
    chunks_count: int
    graph_nodes_count: int = 0
    graph_edges_count: int = 0
    created_at: datetime
    updated_at: datetime
    indexed_at: datetime | None = None

    model_config = {"from_attributes": True}


class DocumentGraphSummary(BaseModel):
    document_id: uuid.UUID
    graph_nodes_count: int
    graph_edges_count: int
    sample_tables: list[str]
