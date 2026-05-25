"""ORM models for persisted repository graph materialization."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.orm_base import Base, JSONBType, UUIDType


class GraphNode(Base):
    """Materialized repository graph node for one commit.

    ``id`` is deterministic and documented in
    ``repository_graph_mapping.stable_graph_node_id``.
    """

    __tablename__ = "graph_nodes"
    __table_args__ = (
        Index("idx_graph_nodes_repo_commit", "repo_id", "commit_sha"),
        Index("idx_graph_nodes_repo_kind", "repo_id", "kind"),
        Index("idx_graph_nodes_repo_path", "repo_id", "path"),
        Index("idx_graph_nodes_attrs", "attrs", postgresql_using="gin"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    repo_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    commit_sha: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str | None] = mapped_column(Text, nullable=True)
    line_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_extractor: Mapped[str] = mapped_column(Text, nullable=False)
    extractor_version: Mapped[str] = mapped_column(Text, nullable=False)
    attrs: Mapped[dict] = mapped_column(JSONBType, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class GraphEdge(Base):
    """Materialized repository graph edge for one commit."""

    __tablename__ = "graph_edges"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    repo_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    commit_sha: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_external: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSONBType, nullable=False)
    confidence: Mapped[str] = mapped_column(Text, nullable=False, server_default="high")
    source_extractor: Mapped[str] = mapped_column(Text, nullable=False)
    extractor_version: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    __table_args__ = (
        CheckConstraint(
            "target_id IS NOT NULL OR target_external IS NOT NULL",
            name="ck_graph_edges_target_present",
        ),
        Index(
            "idx_graph_edges_unique",
            "repo_id",
            "commit_sha",
            "source_id",
            func.coalesce(target_id, target_external),
            "type",
            unique=True,
        ),
        Index("idx_graph_edges_repo_commit", "repo_id", "commit_sha"),
        Index("idx_graph_edges_source", "source_id"),
        Index("idx_graph_edges_target", "target_id"),
    )


class GraphReconciliationRun(Base):
    """Audit summary for one GraphRAG reconciliation run."""

    __tablename__ = "graph_reconciliation_runs"
    __table_args__ = (
        Index(
            "idx_graph_reconciliation_runs_repo_commit_created",
            "repo_id",
            "commit_sha",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    repo_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    commit_sha: Mapped[str] = mapped_column(Text, nullable=False)
    extractor_version: Mapped[str] = mapped_column(Text, nullable=False)
    llm_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    mode: Mapped[str] = mapped_column(Text, nullable=False, server_default="all")
    summary: Mapped[dict] = mapped_column(JSONBType, nullable=False, server_default="{}")
    unresolved: Mapped[list] = mapped_column(JSONBType, nullable=False, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
