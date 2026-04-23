"""ORM models — Agents (perfis de comportamento) e Skills (knowledge base)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.orm_models import Base, UUIDType

# tags: PG_ARRAY(String) em PostgreSQL, JSON em SQLite (testes).
_TagsType = PG_ARRAY(String).with_variant(JSON(), "sqlite")
# embedding: vector(1536) no PG; em SQLite usamos JSON apenas para satisfazer testes
# (não há busca vetorial em SQLite — RAG cai sempre no fallback lexical lá).
_EmbeddingType = Vector(1536).with_variant(JSON(), "sqlite")


class Agent(Base):
    """Perfil de comportamento pré-configurado (system prompt + metadata).

    Uma conversa pode opcionalmente apontar para um Agent — quando aponta,
    o pipeline injeta ``system_prompt`` antes da primeira mensagem do user
    e expõe as Skills associadas ao agente como contexto pesquisável.
    """

    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    icon: Mapped[str] = mapped_column(String(64), nullable=False, default="support_agent")
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    default_model: Mapped[str | None] = mapped_column(String(256), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    skills: Mapped[list["Skill"]] = relationship(
        "Skill", back_populates="agent", cascade="all, delete-orphan"
    )


class Skill(Base):
    """Knowledge base item (documentação/regra/manual) associado a um Agent.

    ``embedding`` é gerado via OpenAI text-embedding-3-small (1536 dims) e
    permite RAG por similaridade cosseno. ``content`` em markdown.
    Quando ``agent_id`` é NULL, a skill é **global** (visível a todos agentes).
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
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("agents.id", ondelete="CASCADE"), nullable=True, index=True
    )
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

    agent: Mapped["Agent | None"] = relationship("Agent", back_populates="skills")
