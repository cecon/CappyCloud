"""ORM models — MCP (Model Context Protocol) server configurations.

Separado em ficheiro próprio para respeitar o limite de 300 linhas por ficheiro.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.orm_base import Base, JSONBType, UUIDType


class McpServer(Base):
    """Servidor MCP configurado por sandbox (ADR-004 §6).

    Cada linha representa uma entrada em ``mcpServers`` no
    ``~/.claude/settings.json`` do openclaude rodando no sandbox.
    Constraint composta ``(sandbox_id, name)`` garante unicidade dentro
    de uma sandbox.
    """

    __tablename__ = "mcp_servers"
    __table_args__ = (UniqueConstraint("sandbox_id", "name", name="uq_mcp_sandbox_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    sandbox_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("sandboxes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    command: Mapped[str] = mapped_column(String(256), nullable=False)
    args: Mapped[list] = mapped_column(JSONBType, nullable=False, server_default="[]")
    env: Mapped[dict] = mapped_column(JSONBType, nullable=False, server_default="{}")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UserMcpServer(Base):
    """Servidor MCP HTTP criado por utilizador para expor um repositório externo.

    O token é guardado somente como hash. ``token_preview`` existe apenas para
    identificação visual no frontend, nunca para autenticação.
    """

    __tablename__ = "user_mcp_servers"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_user_mcp_name"),)

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
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    token_preview: Mapped[str] = mapped_column(String(16), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class McpToolInvocation(Base):
    """Sanitized observability row for one user-scoped MCP tool call."""

    __tablename__ = "mcp_tool_invocations"
    __table_args__ = (
        Index("idx_mcp_invocations_created_at", "created_at"),
        Index("idx_mcp_invocations_tool_created", "tool_name", "created_at"),
        Index("idx_mcp_invocations_repo_created", "repo_id", "created_at"),
        Index("idx_mcp_invocations_trace", "trace_id"),
        Index("idx_mcp_invocations_status_created", "status", "created_at"),
        Index("idx_mcp_invocations_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trace_id: Mapped[uuid.UUID] = mapped_column(UUIDType, nullable=False)
    server_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType,
        ForeignKey("user_mcp_servers.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    repo_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType,
        ForeignKey("repositories.id", ondelete="SET NULL"),
        nullable=True,
    )
    tool_name: Mapped[str] = mapped_column(Text, nullable=False)
    arguments_sanitized: Mapped[dict] = mapped_column(
        JSONBType, nullable=False, server_default="{}"
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    response_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    caller_user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    caller_session_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    meta: Mapped[dict] = mapped_column("metadata", JSONBType, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
