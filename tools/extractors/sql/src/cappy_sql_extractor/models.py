from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cappy_sql_extractor import EXTRACTOR_VERSION, SOURCE_EXTRACTOR


@dataclass(frozen=True)
class StatementText:
    sql: str
    line_start: int
    line_end: int

    @property
    def snippet(self) -> str:
        text = " ".join(self.sql.replace("\r", " ").replace("\n", " ").split())
        return text[:240]


@dataclass
class Graph:
    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    edges: dict[str, dict[str, Any]] = field(default_factory=dict)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def add_node(
        self,
        *,
        node_id: str,
        label: str,
        kind: str,
        name: str,
        path: str,
        statement: StatementText,
        detail: str,
        attrs: dict[str, Any] | None = None,
    ) -> None:
        self.nodes.setdefault(
            node_id,
            {
                "id": node_id,
                "label": label,
                "type": kind,
                "name": name,
                "path": path,
                "file_path": path,
                "line": statement.line_start,
                "line_end": statement.line_end,
                "detail": detail,
                "source_extractor": SOURCE_EXTRACTOR,
                "extractor_version": EXTRACTOR_VERSION,
                "attrs": attrs or {},
            },
        )

    def add_edge(
        self,
        *,
        source: str,
        edge_type: str,
        statement: StatementText,
        file_path: str,
        target: str | None = None,
        target_external: str | None = None,
        confidence: str = "high",
        attrs: dict[str, Any] | None = None,
    ) -> None:
        if not target and not target_external:
            return
        target_key = target or target_external or "unknown"
        edge_id = f"sql:{source}->{target_key}:{edge_type}"
        self.edges.setdefault(
            edge_id,
            {
                "id": edge_id,
                "source": source,
                "target": target or target_external,
                "target_external": target_external,
                "type": edge_type,
                "weight": 1,
                "evidence": {
                    "file": file_path,
                    "line_start": statement.line_start,
                    "line_end": statement.line_end,
                    "snippet": statement.snippet,
                },
                "confidence": confidence,
                "source_extractor": SOURCE_EXTRACTOR,
                "extractor_version": EXTRACTOR_VERSION,
                "attrs": attrs or {},
            },
        )

    def diagnostic(
        self,
        *,
        level: str,
        phase: str,
        message: str,
        file_path: str = "",
        line: int = 0,
    ) -> None:
        self.diagnostics.append(
            {
                "level": level,
                "phase": phase,
                "file": file_path,
                "line": line,
                "message": message,
            }
        )
