"""ORM models — MCP (Model Context Protocol) server configurations.

Separado em ficheiro próprio para respeitar o limite de 300 linhas por ficheiro.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
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
