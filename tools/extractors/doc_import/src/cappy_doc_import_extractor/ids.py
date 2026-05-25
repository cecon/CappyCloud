from __future__ import annotations

import re

_SPACE_RE = re.compile(r"\s+")


def materialized_doc_node_id(
    *,
    repo_id: str,
    commit_sha: str,
    document_id: str,
    kind: str,
    qualified_name: str,
) -> str:
    return (
        f"repo:{repo_id}@{commit_sha}:doc:{document_id}"
        f"#{kind}:{_safe_id_part(qualified_name)}"
    )


def edge_id(
    source: str, edge_type: str, target: str | None, target_external: str | None
) -> str:
    return f"doc:{source}->{target or target_external}:{edge_type}"


def _safe_id_part(value: str) -> str:
    cleaned = _SPACE_RE.sub(" ", str(value or "")).strip()
    return cleaned.replace("#", "%23").replace("<", "__").replace(">", "__") or "node"
