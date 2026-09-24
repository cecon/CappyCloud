"""ORM models — workspaces (pasta de trabalho com vários repositórios).

Um workspace é criado pelo super admin, vive numa sandbox e agrupa repositórios
do catálogo. No sandbox vira ``/repos/workspaces/<slug>/`` com ``CLAUDE.md``,
``.claude/``, conhecimento e ``repos/<alias>`` apontando para o clone do catálogo.

sync_status: pending | synced | error
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.orm_base import Base, UUIDType


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    sandbox_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("sandboxes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    claude_md: Mapped[str] = mapped_column(Text, nullable=False, server_default="", default="")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sync_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="pending", default="pending"
    )
    sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    repositories: Mapped[list[WorkspaceRepository]] = relationship(
        "WorkspaceRepository",
        back_populates="workspace",
        cascade="all, delete-orphan",
        order_by="WorkspaceRepository.alias",
    )


class WorkspaceRepository(Base):
    """Repositório do catálogo vinculado a um workspace, com alias próprio."""

    __tablename__ = "workspace_repositories"
    __table_args__ = (
        UniqueConstraint("workspace_id", "repository_id", name="uq_workspace_repository"),
        UniqueConstraint("workspace_id", "alias", name="uq_workspace_repository_alias"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    alias: Mapped[str] = mapped_column(String(128), nullable=False)
    # Vazio = usa a default_branch do repositório.
    base_branch: Mapped[str] = mapped_column(String(256), nullable=False, server_default="")
    # Somente leitura: sem worktree/branch na sessão, fora do diff e do PR.
    read_only: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    workspace: Mapped[Workspace] = relationship("Workspace", back_populates="repositories")
    repository: Mapped["Repository"] = relationship("Repository")  # type: ignore[name-defined]  # noqa: F821


class UserWorkspaceAccess(Base):
    """Acesso binário user → workspace (concedido pelo super admin)."""

    __tablename__ = "user_workspace_access"
    __table_args__ = (UniqueConstraint("user_id", "workspace_id", name="uq_user_workspace_access"),)

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
