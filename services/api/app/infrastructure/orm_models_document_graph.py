"""ORM models for document-scoped schema graphs."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.orm_base import Base, JSONBType, UUIDType


class DocumentGraphNode(Base):
    """Node extracted from a repository document.

    The graph is scoped by ``document_id`` and cascades with the document so
    reindex/delete cannot leave stale graph data behind.
    """

    __tablename__ = "document_graph_nodes"
    __table_args__ = (
        UniqueConstraint("document_id", "node_key", name="uq_document_graph_nodes_doc_key"),
        Index("idx_document_graph_nodes_repo_kind", "repository_id", "kind"),
        Index("idx_document_graph_nodes_name", "name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    node_key: Mapped[str] = mapped_column(String(512), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    attrs: Mapped[dict] = mapped_column(JSONBType, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    outgoing_edges: Mapped[list["DocumentGraphEdge"]] = relationship(
        "DocumentGraphEdge",
        foreign_keys="DocumentGraphEdge.source_node_id",
        cascade="all, delete-orphan",
    )


class DocumentGraphEdge(Base):
    """Directed relation extracted from a repository document graph."""

    __tablename__ = "document_graph_edges"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "source_node_id",
            "target_node_id",
            "target_key",
            "edge_type",
            name="uq_document_graph_edges_doc_relation",
        ),
        Index("idx_document_graph_edges_repo_type", "repository_id", "edge_type"),
        Index("idx_document_graph_edges_target_key", "target_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("document_graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType,
        ForeignKey("document_graph_nodes.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    target_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    edge_type: Mapped[str] = mapped_column(String(64), nullable=False)
    attrs: Mapped[dict] = mapped_column(JSONBType, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
