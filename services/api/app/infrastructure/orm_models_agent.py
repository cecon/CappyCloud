"""ORM models — Skills (knowledge base)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.orm_base import Base, UUIDType

# tags: PG_ARRAY(String) em PostgreSQL, JSON em SQLite (testes).
_TagsType = PG_ARRAY(String).with_variant(JSON(), "sqlite")
# embedding: vector(1536) no PG; em SQLite usamos JSON apenas para satisfazer testes
# (não há busca vetorial em SQLite — RAG cai sempre no fallback lexical lá).
_EmbeddingType = Vector(1536).with_variant(JSON(), "sqlite")


class Skill(Base):
    """Knowledge base item (documentação/regra/manual) associado a repositórios.

    ``embedding`` é gerado via OpenAI text-embedding-3-small (1536 dims) e
    permite RAG por similaridade cosseno. ``content`` em markdown.
    """

    __tablename__ = "skills"
    __table_args__ = (
        Index(
            "ix_skills_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True
    )
    chunk_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    slug: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(_TagsType, nullable=False, server_default="{}")
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(_EmbeddingType, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    repository: Mapped["Repository | None"] = relationship(  # type: ignore[name-defined]
        "Repository", foreign_keys=[repository_id]
    )
