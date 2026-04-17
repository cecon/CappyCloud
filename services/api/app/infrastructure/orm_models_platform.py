"""ORM models — Platform control plane entities.

Git providers, AI providers/models, repositories, and sandbox sync queue.
Separated from orm_models.py to keep file size under the 300-line limit.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.orm_models import Base, JSONBType, UUIDType


class GitProvider(Base):
    """Provedor de repositórios git com token PAT criptografado.

    provider_type: github | azure_devops | gitlab | bitbucket
    """

    __tablename__ = "git_providers"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="github", index=True
    )
    base_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    org_or_project: Mapped[str] = mapped_column(Text, nullable=False, default="")
    token_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    repositories: Mapped[list["Repository"]] = relationship("Repository", back_populates="provider")


class AiProvider(Base):
    """Provedor de modelos IA (OpenRouter, Anthropic, OpenAI…)."""

    __tablename__ = "ai_providers"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    base_url: Mapped[str] = mapped_column(
        Text, nullable=False, default="https://openrouter.ai/api/v1"
    )
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    models: Mapped[list["AiModel"]] = relationship(
        "AiModel", back_populates="provider", cascade="all, delete-orphan"
    )


class AiModel(Base):
    """Modelo IA com capabilities e flags de default por capability.

    capabilities: JSONB ['text', 'vision', 'embedding', 'video']
    is_default:   JSONB {'text': true, 'vision': false, ...}
    """

    __tablename__ = "ai_models"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("ai_providers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_id: Mapped[str] = mapped_column(String(256), nullable=False)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    capabilities: Mapped[list] = mapped_column(JSONBType, nullable=False, server_default='["text"]')
    is_default: Mapped[dict] = mapped_column(JSONBType, nullable=False, server_default="{}")
    context_window: Mapped[int] = mapped_column(Integer, nullable=False, default=200000)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    provider: Mapped["AiProvider"] = relationship("AiProvider", back_populates="models")
    conversations: Mapped[list["Conversation"]] = relationship(  # type: ignore[name-defined]
        "Conversation", back_populates="ai_model"
    )


class Repository(Base):
    """Repositório git com estado de sincronização no sandbox.

    sandbox_status: not_cloned | cloning | cloned | error
    """

    __tablename__ = "repositories"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("git_providers.id", ondelete="SET NULL"), nullable=True
    )
    clone_url: Mapped[str] = mapped_column(Text, nullable=False)
    default_branch: Mapped[str] = mapped_column(String(256), nullable=False, default="main")
    sandbox_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("sandboxes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    sandbox_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="not_cloned", index=True
    )
    sandbox_path: Mapped[str] = mapped_column(Text, nullable=False, default="")
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    provider: Mapped["GitProvider | None"] = relationship(
        "GitProvider", back_populates="repositories"
    )
    sandbox: Mapped["Sandbox | None"] = relationship(  # type: ignore[name-defined]
        "Sandbox", back_populates="repositories"
    )


class SandboxSyncQueue(Base):
    """Fila de sincronização DB → sandbox VM (watchdog).

    operation: clone_repo | remove_repo | update_git_auth | reconfigure_model
    status:    pending | processing | done | error
    """

    __tablename__ = "sandbox_sync_queue"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    sandbox_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("sandboxes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONBType, nullable=False, server_default="{}")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sandbox: Mapped["Sandbox"] = relationship(  # type: ignore[name-defined]
        "Sandbox", back_populates="sync_queue"
    )
