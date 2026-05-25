from __future__ import annotations

import hashlib


def original_edge_key(
    *,
    repo_id: str,
    commit_sha: str,
    source_id: str,
    target_external: str,
    edge_type: str,
) -> str:
    raw = f"{repo_id}:{commit_sha}:{source_id}:{target_external}:{edge_type}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
