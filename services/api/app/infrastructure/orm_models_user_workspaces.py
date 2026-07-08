"""SQLAlchemy models for per-user repository workspace baselines."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.value_objects import DEFAULT_USER_WORKSPACE_STATUS
from app.infrastructure.orm_base import Base, UUIDType


class UserRepositoryWorkspace(Base):
    __tablename__ = "user_repository_workspaces"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "repository_id",
            "sandbox_key",
            "base_branch",
            name="uq_user_repo_workspace_scope",
        ),
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
    sandbox_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType,
        ForeignKey("sandboxes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sandbox_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        server_default="default",
        default="default",
        index=True,
    )
    base_branch: Mapped[str] = mapped_column(String(256), nullable=False)
    workspace_path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=DEFAULT_USER_WORKSPACE_STATUS,
        default=DEFAULT_USER_WORKSPACE_STATUS,
        index=True,
    )
    health_message: Mapped[str] = mapped_column(Text, nullable=False, server_default="", default="")
    last_prepared_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
