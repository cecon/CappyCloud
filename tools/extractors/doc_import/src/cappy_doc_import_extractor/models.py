from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cappy_doc_import_extractor import EXTRACTOR_VERSION, SOURCE_EXTRACTOR


@dataclass(frozen=True)
class Chunk:
    id: str
    index: int
    content: str
    line_start: int = 1
    line_end: int = 1


@dataclass(frozen=True)
class SourceDocument:
    id: str
    repo_id: str
    source_type: str
    title: str
    source_uri: str
    chunks_count: int
    indexed_at: str | None
    chunks: list[Chunk]

    @property
    def filename(self) -> str:
        return self.source_uri or self.title or str(self.id)

    @property
    def text(self) -> str:
        return "".join(chunk.content for chunk in self.chunks)

    def chunk_index_for_line(self, line: int) -> int:
        for chunk in self.chunks:
            if chunk.line_start <= line <= chunk.line_end:
                return chunk.index
        return self.chunks[-1].index if self.chunks else 0


@dataclass
class Graph:
    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    edges: dict[str, dict[str, Any]] = field(default_factory=dict)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def add_node(
        self,
        *,
        node_id: str,
        kind: str,
        name: str,
        label: str,
        file_path: str,
        line: int,
        line_end: int,
        detail: str,
        attrs: dict[str, Any],
    ) -> None:
        self.nodes.setdefault(
            node_id,
            {
                "id": node_id,
                "label": label,
                "type": kind,
                "name": name,
                "path": file_path,
                "file_path": file_path,
                "line": line,
                "line_end": line_end,
                "detail": detail,
                "source_extractor": SOURCE_EXTRACTOR,
                "extractor_version": EXTRACTOR_VERSION,
                "attrs": attrs,
            },
        )

    def add_edge(
        self,
        *,
        edge_id: str,
        source: str,
        edge_type: str,
        evidence: dict[str, Any],
        attrs: dict[str, Any],
        target: str | None = None,
        target_external: str | None = None,
        confidence: str = "high",
    ) -> None:
        if not target and not target_external:
            return
        self.edges.setdefault(
            edge_id,
            {
                "id": edge_id,
                "source": source,
                "target": target or target_external,
                "target_external": target_external,
                "type": edge_type,
                "weight": 1,
                "evidence": evidence,
                "confidence": confidence,
                "source_extractor": SOURCE_EXTRACTOR,
                "extractor_version": EXTRACTOR_VERSION,
                "attrs": attrs,
            },
        )

    def diagnostic(
        self,
        *,
        document_id: str,
        level: str,
        code: str,
        message: str,
        line: int = 0,
        chunk_index: int | None = None,
    ) -> None:
        self.diagnostics.append(
            {
                "document_id": document_id,
                "level": level,
                "code": code,
                "message": message,
                "line": line,
                "chunk_index": chunk_index,
            }
        )
