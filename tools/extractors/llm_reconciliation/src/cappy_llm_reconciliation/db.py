from __future__ import annotations

import json
import uuid
from typing import Any

import asyncpg

from cappy_llm_reconciliation.models import Candidate, RefEdge


async def load_inputs(
    *,
    db_url: str,
    repo_id: str,
    commit_sha: str,
    limit: int | None = None,
) -> tuple[list[RefEdge], list[Candidate]]:
    conn = await asyncpg.connect(db_url)
    try:
        refs = await _fetch_refs(
            conn, repo_id=repo_id, commit_sha=commit_sha, limit=limit
        )
        candidates = await _fetch_candidates(
            conn, repo_id=repo_id, commit_sha=commit_sha
        )
        await _attach_chunks(conn, repo_id=repo_id, candidates=candidates)
        return refs, candidates
    finally:
        await conn.close()


async def _fetch_refs(
    conn: asyncpg.Connection,
    *,
    repo_id: str,
    commit_sha: str,
    limit: int | None,
) -> list[RefEdge]:
    sql = """
        SELECT source_id, target_external, type, evidence
        FROM graph_edges
        WHERE repo_id = $1 AND commit_sha = $2
          AND source_extractor = 'static_roslyn'
          AND (
            target_external LIKE 'ref:%'
            OR (type = 'maps_to_table' AND target_external LIKE 'table:%')
          )
        ORDER BY source_id, target_external, type
    """
    args: list[Any] = [uuid.UUID(repo_id), commit_sha]
    if limit and limit > 0:
        sql += " LIMIT $3"
        args.append(limit)
    rows = await conn.fetch(sql, *args)
    return [
        RefEdge(
            source_id=str(row["source_id"]),
            target_external=str(row["target_external"]),
            edge_type=str(row["type"]),
            evidence=_json_obj(row["evidence"]),
        )
        for row in rows
    ]


async def _fetch_candidates(
    conn: asyncpg.Connection,
    *,
    repo_id: str,
    commit_sha: str,
) -> list[Candidate]:
    rows = await conn.fetch(
        """
        SELECT id, kind, name, source_extractor, attrs, commit_sha, created_at
        FROM graph_nodes
        WHERE repo_id = $1
          AND kind IN ('table', 'column')
          AND source_extractor IN ('doc_import', 'static_sql')
        ORDER BY (commit_sha = $2) DESC, created_at DESC
        """,
        uuid.UUID(repo_id),
        commit_sha,
    )
    seen: set[tuple[str, str]] = set()
    candidates: list[Candidate] = []
    for row in rows:
        attrs = _json_obj(row["attrs"])
        qualified = _qualified_name(str(row["id"]), str(row["name"]), str(row["kind"]))
        key = (str(row["kind"]), qualified.lower())
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            Candidate(
                id=str(row["id"]),
                kind=str(row["kind"]),
                name=_short_name(qualified),
                qualified_name=qualified,
                source_extractor=str(row["source_extractor"]),
                document_id=_optional_str(attrs.get("document_id")),
                chunk_index=_optional_int(attrs.get("chunk_index")),
            )
        )
    return candidates


async def _attach_chunks(
    conn: asyncpg.Connection,
    *,
    repo_id: str,
    candidates: list[Candidate],
) -> None:
    document_ids = sorted(
        {
            uuid.UUID(c.document_id)
            for c in candidates
            if c.document_id and c.chunk_index is not None
        }
    )
    if not document_ids:
        return
    rows = await conn.fetch(
        """
        SELECT document_id::text, chunk_index, content, embedding::text AS embedding
        FROM skills
        WHERE repository_id = $1
          AND active = TRUE
          AND document_id = ANY($2::uuid[])
        """,
        uuid.UUID(repo_id),
        document_ids,
    )
    chunk_map = {
        (str(row["document_id"]), int(row["chunk_index"])): (
            str(row["content"] or ""),
            _parse_embedding(row["embedding"]),
        )
        for row in rows
    }
    for index, candidate in enumerate(candidates):
        if candidate.document_id is None or candidate.chunk_index is None:
            continue
        content, embedding = chunk_map.get(
            (candidate.document_id, candidate.chunk_index), ("", None)
        )
        candidates[index] = Candidate(
            **{
                **candidate.__dict__,
                "chunk_excerpt": _excerpt(content),
                "embedding": embedding,
            }
        )


def _qualified_name(node_id: str, fallback: str, kind: str) -> str:
    marker = f"#{kind}:"
    if marker in node_id:
        return node_id.rsplit(marker, 1)[-1]
    return fallback


def _short_name(qualified: str) -> str:
    return qualified.split(".")[-1]


def _excerpt(content: str, limit: int = 700) -> str:
    cleaned = " ".join((content or "").split())
    return cleaned[:limit]


def _parse_embedding(value: Any) -> list[float] | None:
    if isinstance(value, list):
        return [float(item) for item in value]
    text = str(value or "").strip().strip("[]")
    if not text:
        return None
    try:
        return [float(part) for part in text.split(",") if part.strip()]
    except ValueError:
        return None


def _json_obj(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _optional_str(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed
