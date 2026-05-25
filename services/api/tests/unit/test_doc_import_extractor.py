from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT / "tools" / "extractors" / "doc_import" / "src"))

from cappy_doc_import_extractor.dispatcher import extract_document  # noqa: E402
from cappy_doc_import_extractor.models import Chunk, Graph, SourceDocument  # noqa: E402

API_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = API_ROOT / "tests" / "fixtures"


def _document(text: str, source_type: str = "markdown") -> SourceDocument:
    return SourceDocument(
        id="fdf8a57c-4042-4bda-99d0-ea20b2167cd8",
        repo_id="e41b15fa-5da8-4930-b741-ad3d2d859b45",
        source_type=source_type,
        title="DATABASE_SCHEMA_Edu_CBE_2.md",
        source_uri="DATABASE_SCHEMA_Edu_CBE_2.md",
        chunks_count=1,
        indexed_at="2026-05-22T22:41:06Z",
        chunks=[Chunk(id="chunk-1", index=0, content=text, line_start=1, line_end=80)],
    )


def test_markdown_schema_catalog_parser_emits_snapshot_counts() -> None:
    graph = Graph()
    text = (FIXTURES / "doc_import_schema_catalog.md").read_text(encoding="utf-8")

    extract_document(graph=graph, document=_document(text), repo_id="repo-1", commit_sha="abc123")

    nodes = list(graph.nodes.values())
    edges = list(graph.edges.values())
    assert _count(nodes, "type") == {"document": 1, "table": 5, "column": 11}
    assert _count(edges, "type") == {"defines": 16, "foreign_key": 4}
    assert any(
        edge["type"] == "foreign_key"
        and edge["target"].endswith("#column:dbo.tenants.id")
        and edge["confidence"] == "high"
        for edge in edges
    )
    assert any(
        edge["type"] == "foreign_key"
        and edge["target_external"] == "table:external.users.id"
        and edge["confidence"] == "medium"
        for edge in edges
    )
    assert any(
        diagnostic["code"] == "unmatched_line" and diagnostic["level"] == "info"
        for diagnostic in graph.diagnostics
    )
    assert all(node["attrs"]["document_id"] for node in nodes)
    assert all(
        "chunk_index" in node["attrs"] for node in nodes if node["type"] in {"table", "column"}
    )


def test_dispatcher_reports_unsupported_markdown_without_nodes() -> None:
    graph = Graph()

    extract_document(
        graph=graph,
        document=_document("# Manual\n\nSem catálogo estrutural."),
        repo_id="repo-1",
        commit_sha="abc123",
    )

    assert graph.nodes == {}
    assert graph.edges == {}
    assert graph.diagnostics == [
        {
            "document_id": "fdf8a57c-4042-4bda-99d0-ea20b2167cd8",
            "level": "warning",
            "code": "unsupported_format",
            "message": "unsupported source_type=markdown",
            "line": 0,
            "chunk_index": None,
        }
    ]


def _count(items: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item[key]] = counts.get(item[key], 0) + 1
    return counts
