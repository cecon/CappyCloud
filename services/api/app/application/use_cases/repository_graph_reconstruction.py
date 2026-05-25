"""Rebuild the public repository graph JSON shape from materialized rows."""

from __future__ import annotations

from typing import Any


def reconstruct_graph_from_rows(
    *,
    repo_slug: str,
    repo_path: str,
    nodes: list[Any],
    edges: list[Any],
) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = {
        "nodes": [],
        "files": [],
        "symbols": [],
        "semantic_nodes": [],
        "edges": [],
        "file_edges": [],
        "semantic_edges": [],
    }
    meta: dict[str, Any] = {}
    for node in nodes:
        attrs = dict(node.attrs or {})
        bucket = str(attrs.get("bucket") or "")
        sandbox = attrs.get("sandbox")
        if bucket in buckets and isinstance(sandbox, dict):
            buckets[bucket].append(sandbox)
        if isinstance(attrs.get("graph_meta"), dict):
            meta = attrs["graph_meta"]
    for edge in edges:
        evidence = dict(edge.evidence or {})
        bucket = str(evidence.get("bucket") or "")
        sandbox = evidence.get("sandbox")
        if bucket in buckets and isinstance(sandbox, dict):
            buckets[bucket].append(sandbox)

    return {
        "slug": meta.get("slug") or repo_slug,
        "repo_path": meta.get("repo_path") or repo_path,
        "generated_at": meta.get("generated_at") or "",
        "stats": meta.get("stats") or _stats_from_buckets(buckets),
        "nodes": buckets["nodes"],
        "edges": buckets["edges"],
        "files": buckets["files"],
        "symbols": buckets["symbols"],
        "file_edges": buckets["file_edges"],
        "semantic_nodes": buckets["semantic_nodes"],
        "semantic_edges": buckets["semantic_edges"],
        "findings": meta.get("findings") or [],
    }


def _stats_from_buckets(buckets: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    return {
        "files": len(buckets["files"]),
        "code_files": len(buckets["files"]),
        "modules": len(buckets["nodes"]),
        "links": len(buckets["file_edges"]),
        "isolated": 0,
        "symbols": len(buckets["symbols"]),
        "entrypoints": 0,
        "unreferenced_files": 0,
        "ui_actions": len([s for s in buckets["symbols"] if s.get("kind") == "ui_action"]),
        "flows": len(buckets["semantic_edges"]),
    }
