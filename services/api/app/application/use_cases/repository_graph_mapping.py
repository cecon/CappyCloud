"""Translation between sandbox repository graph JSON and persisted rows."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any, cast

SOURCE_EXTRACTOR = "static_js"
EXTRACTOR_VERSION = "0.1.0"
DOC_IMPORT_SOURCE = "doc_import"

_SAFE_ID_RE = re.compile(r"\s+")
_SEMANTIC_KIND_MAP = {"data": "table"}
_SQL_NODE_KINDS = {
    "sql_file",
    "table",
    "column",
    "view",
    "index",
    "constraint",
    "stored_procedure",
    "trigger",
}


@dataclass(frozen=True)
class GraphNodeInsert:
    id: str
    repo_id: uuid.UUID
    commit_sha: str
    kind: str
    name: str
    path: str | None
    line_start: int | None
    line_end: int | None
    source_extractor: str
    extractor_version: str
    attrs: dict[str, Any]


@dataclass(frozen=True)
class GraphEdgeInsert:
    repo_id: uuid.UUID
    commit_sha: str
    source_id: str
    target_id: str | None
    target_external: str | None
    type: str
    evidence: dict[str, Any]
    confidence: str
    source_extractor: str
    extractor_version: str


@dataclass(frozen=True)
class GraphMaterializationRows:
    nodes: list[GraphNodeInsert]
    edges: list[GraphEdgeInsert]


def stable_graph_node_id(
    repo_id: uuid.UUID | str,
    commit_sha: str,
    *,
    kind: str,
    name: str,
    path: str | None = None,
    disambiguator: str | None = None,
) -> str:
    """Build deterministic ids scoped by ``repo:{repo_id}@{commit_sha}``.

    File nodes use ``:file:{path}``; symbols use ``:file:{path}#{qualified_name}``.
    Duplicate sandbox symbols keep that base and append ``@{sandbox_id}``.
    """
    safe_name = _normalise_id_part(name)
    if path and kind in _SQL_NODE_KINDS:
        node_id = f"repo:{repo_id}@{commit_sha}:sql:{path}#{kind}:{safe_name}"
    elif path:
        base = f"repo:{repo_id}@{commit_sha}:file:{path}"
        node_id = (
            base
            if kind == "file" and safe_name == _normalise_id_part(path)
            else f"{base}#{safe_name}"
        )
    else:
        node_id = f"repo:{repo_id}@{commit_sha}:{kind}:{safe_name}"
    if disambiguator:
        return f"{node_id}@{_normalise_id_part(disambiguator)}"
    return node_id


def translate_sandbox_graph(
    *,
    repo_id: uuid.UUID,
    commit_sha: str,
    graph: dict[str, Any],
) -> GraphMaterializationRows:
    """Translate the current sandbox graph JSON shape into DB insert rows."""
    node_rows: list[GraphNodeInsert] = []
    edge_rows: list[GraphEdgeInsert] = []
    id_map: dict[str, str] = {}
    node_evidence: dict[str, tuple[str | None, int | None, int | None]] = {}
    extractor_version = str(graph.get("extractor_version") or EXTRACTOR_VERSION)

    graph_meta = {
        "slug": graph.get("slug"),
        "repo_path": graph.get("repo_path"),
        "generated_at": graph.get("generated_at"),
        "stats": graph.get("stats") or {},
        "findings": graph.get("findings") or [],
    }
    seen_node_ids: set[str] = set()

    def add_node(item: dict[str, Any], bucket: str) -> None:
        row = _node_from_sandbox(
            repo_id=repo_id,
            commit_sha=commit_sha,
            item=item,
            bucket=bucket,
            graph_meta=graph_meta if bucket == "nodes" and item.get("type") == "repo" else None,
            extractor_version=extractor_version,
        )
        if row.id in seen_node_ids:
            row = _node_from_sandbox(
                repo_id=repo_id,
                commit_sha=commit_sha,
                item=item,
                bucket=bucket,
                graph_meta=(
                    graph_meta if bucket == "nodes" and item.get("type") == "repo" else None
                ),
                extractor_version=extractor_version,
                disambiguator=str(item.get("id") or len(seen_node_ids)),
            )
        seen_node_ids.add(row.id)
        node_rows.append(row)
        sandbox_id = str(item.get("id") or "")
        if sandbox_id:
            id_map[sandbox_id] = row.id
            node_evidence[sandbox_id] = (row.path, row.line_start, row.line_end)

    for item in _items(graph, "nodes"):
        add_node(item, "nodes")
    for item in _items(graph, "files"):
        add_node(item, "files")
    for item in _items(graph, "symbols"):
        add_node(item, "symbols")
    for item in _items(graph, "semantic_nodes"):
        add_node(item, "semantic_nodes")

    for bucket in ("edges", "file_edges", "semantic_edges"):
        for edge in _items(graph, bucket):
            edge_rows.append(
                _edge_from_sandbox(
                    repo_id=repo_id,
                    commit_sha=commit_sha,
                    edge=edge,
                    bucket=bucket,
                    id_map=id_map,
                    node_evidence=node_evidence,
                    extractor_version=extractor_version,
                )
            )

    return GraphMaterializationRows(nodes=node_rows, edges=edge_rows)


def _node_from_sandbox(
    *,
    repo_id: uuid.UUID,
    commit_sha: str,
    item: dict[str, Any],
    bucket: str,
    graph_meta: dict[str, Any] | None,
    extractor_version: str,
    disambiguator: str | None = None,
) -> GraphNodeInsert:
    kind = _node_kind(item, bucket)
    path = _node_path(item, bucket)
    name = _node_name(item, kind, path)
    line = _as_int(item.get("line"))
    line_end = _as_int(item.get("line_end")) or line
    attrs: dict[str, Any] = {"bucket": bucket, "sandbox": item}
    item_attrs = item.get("attrs")
    if isinstance(item_attrs, dict):
        attrs.update(cast(dict[str, Any], item_attrs))
    if graph_meta is not None:
        attrs["graph_meta"] = graph_meta
    source_extractor = _source_extractor(item)
    item_version = _extractor_version(item, extractor_version)
    return GraphNodeInsert(
        id=_explicit_node_id(item, source_extractor)
        or stable_graph_node_id(
            repo_id,
            commit_sha,
            kind=kind,
            name=name,
            path=path,
            disambiguator=disambiguator,
        ),
        repo_id=repo_id,
        commit_sha=commit_sha,
        kind=kind,
        name=name,
        path=path,
        line_start=line,
        line_end=line_end,
        source_extractor=source_extractor,
        extractor_version=item_version,
        attrs=attrs,
    )


def _edge_from_sandbox(
    *,
    repo_id: uuid.UUID,
    commit_sha: str,
    edge: dict[str, Any],
    bucket: str,
    id_map: dict[str, str],
    node_evidence: dict[str, tuple[str | None, int | None, int | None]],
    extractor_version: str,
) -> GraphEdgeInsert:
    source = str(edge.get("source") or "")
    target = str(edge.get("target") or "")
    explicit_target_external = str(edge.get("target_external") or "")
    source_id = id_map.get(source) or (
        source
        if source.startswith("repo:")
        else stable_graph_node_id(
            repo_id,
            commit_sha,
            kind="external",
            name=source or "unknown",
        )
    )
    target_id = None if explicit_target_external else id_map.get(target)
    if target_id is None and target.startswith("repo:"):
        target_id = target
    file_path, line_start, line_end = node_evidence.get(source, (None, None, None))
    raw_evidence = edge.get("evidence")
    edge_evidence: dict[str, Any] = (
        cast(dict[str, Any], raw_evidence) if isinstance(raw_evidence, dict) else {}
    )
    evidence = {
        "file": edge_evidence.get("file") or file_path,
        "line_start": _as_int(edge_evidence.get("line_start")) or line_start,
        "line_end": _as_int(edge_evidence.get("line_end")) or line_end,
        "snippet": edge_evidence.get("snippet"),
        "bucket": bucket,
        "sandbox": edge,
    }
    if isinstance(edge.get("attrs"), dict):
        evidence["attrs"] = edge["attrs"]
    source_extractor = _source_extractor(edge)
    item_version = _extractor_version(edge, extractor_version)
    target_external = explicit_target_external or (None if target_id else target or "unknown")
    return GraphEdgeInsert(
        repo_id=repo_id,
        commit_sha=commit_sha,
        source_id=source_id,
        target_id=target_id,
        target_external=target_external,
        type=str(edge.get("type") or "related"),
        evidence=evidence,
        confidence=_edge_confidence(edge, evidence),
        source_extractor=source_extractor,
        extractor_version=item_version,
    )


def _items(graph: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = graph.get(key) or []
    return [item for item in value if isinstance(item, dict)]


def _node_kind(item: dict[str, Any], bucket: str) -> str:
    if bucket == "files":
        return "file"
    if bucket == "symbols":
        return str(item.get("kind") or "symbol")
    raw = str(item.get("type") or "node")
    return _SEMANTIC_KIND_MAP.get(raw, raw)


def _node_path(item: dict[str, Any], bucket: str) -> str | None:
    if bucket == "files":
        return str(item.get("path") or "") or None
    return str(item.get("file_path") or item.get("path") or "") or None


def _node_name(item: dict[str, Any], kind: str, path: str | None) -> str:
    if kind == "file" and path:
        return path
    container = str(item.get("container") or "").strip()
    name = str(item.get("name") or item.get("label") or item.get("id") or "").strip()
    return f"{container}.{name}" if container and name else name or path or "node"


def _normalise_id_part(value: str) -> str:
    cleaned = _SAFE_ID_RE.sub(" ", str(value or "")).strip()
    return cleaned.replace("#", "%23").replace("<", "__").replace(">", "__") or "node"


def _explicit_node_id(item: dict[str, Any], source_extractor: str) -> str | None:
    node_id = str(item.get("id") or "")
    if source_extractor == DOC_IMPORT_SOURCE and node_id.startswith("repo:"):
        return node_id
    return None


def _as_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except TypeError, ValueError:
        return None
    return parsed if parsed > 0 else None


def _source_extractor(item: dict[str, Any]) -> str:
    return str(item.get("source_extractor") or SOURCE_EXTRACTOR)


def _extractor_version(item: dict[str, Any], fallback: str) -> str:
    return str(item.get("extractor_version") or fallback or EXTRACTOR_VERSION)


def _edge_confidence(edge: dict[str, Any], evidence: dict[str, Any]) -> str:
    confidence = str(edge.get("confidence") or "").strip()
    if confidence:
        return confidence
    return "medium" if not evidence.get("line_start") or evidence.get("snippet") is None else "high"
