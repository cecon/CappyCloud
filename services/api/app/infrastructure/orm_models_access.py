"""ORM models — permissões binárias user → recurso (ADR-005 §2).

3 tabelas associativas (user_sandbox_access, user_repository_access,
user_ai_model_access) com FK CASCADE em ambos os lados e UNIQUE composta
para evitar duplicação.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.orm_base import Base, UUIDType


class UserSandboxAccess(Base):
    """Acesso binário user → sandbox."""

    __tablename__ = "user_sandbox_access"
    __table_args__ = (UniqueConstraint("user_id", "sandbox_id", name="uq_user_sandbox_access"),)

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sandbox_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("sandboxes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserRepositoryAccess(Base):
    """Acesso binário user → repository."""

    __tablename__ = "user_repository_access"
    __table_args__ = (
        UniqueConstraint("user_id", "repository_id", name="uq_user_repository_access"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserAiModelAccess(Base):
    """Acesso binário user → ai_model."""

    __tablename__ = "user_ai_model_access"
    __table_args__ = (UniqueConstraint("user_id", "ai_model_id", name="uq_user_ai_model_access"),)

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ai_model_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("ai_models.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
