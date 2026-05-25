from __future__ import annotations

import re
from collections import defaultdict

import asyncpg

from cappy_doc_import_extractor.models import Chunk, SourceDocument

_ASYNC_DSN_RE = re.compile(r"^postgresql\+asyncpg://", re.I)


def normalize_db_url(db_url: str) -> str:
    return _ASYNC_DSN_RE.sub("postgresql://", db_url.strip())


async def load_documents(
    *,
    db_url: str,
    repo_id: str,
    document_ids: list[str] | None = None,
) -> list[SourceDocument]:
    conn = await asyncpg.connect(normalize_db_url(db_url))
    try:
        rows = await conn.fetch(_query(document_ids), *(_params(repo_id, document_ids)))
    finally:
        await conn.close()
    grouped: dict[str, list[asyncpg.Record]] = defaultdict(list)
    for row in rows:
        grouped[str(row["document_id"])].append(row)

    documents: list[SourceDocument] = []
    for doc_rows in grouped.values():
        first = doc_rows[0]
        chunks = _chunks(doc_rows)
        documents.append(
            SourceDocument(
                id=str(first["document_id"]),
                repo_id=str(first["repository_id"]),
                source_type=str(first["source_type"]),
                title=str(first["title"]),
                source_uri=str(first["source_uri"] or ""),
                chunks_count=int(first["chunks_count"] or len(chunks)),
                indexed_at=first["indexed_at"].isoformat() if first["indexed_at"] else None,
                chunks=chunks,
            )
        )
    return documents


def _query(document_ids: list[str] | None) -> str:
    filter_sql = ""
    if document_ids:
        placeholders = ", ".join(f"${index}::uuid" for index in range(2, len(document_ids) + 2))
        filter_sql = f"AND d.id IN ({placeholders})"
    return f"""
        SELECT
            d.id AS document_id,
            d.repository_id,
            d.source_type,
            d.source_uri,
            d.title,
            d.chunks_count,
            d.indexed_at,
            s.id AS skill_id,
            s.chunk_index,
            s.content
        FROM documents d
        JOIN skills s ON s.document_id = d.id
        WHERE d.repository_id = $1::uuid
          AND d.status = 'indexed'
          AND d.source_type IN ('markdown')
          AND s.active = TRUE
          {filter_sql}
        ORDER BY d.id, s.chunk_index
    """


def _params(repo_id: str, document_ids: list[str] | None) -> list[str]:
    return [repo_id, *(document_ids or [])]


def _chunks(rows: list[asyncpg.Record]) -> list[Chunk]:
    chunks: list[Chunk] = []
    text_so_far = ""
    next_line = 1
    for row in rows:
        raw_content = str(row["content"] or "")
        content = _non_overlapping_suffix(text_so_far, raw_content)
        if not content:
            continue
        line_count = max(1, content.count("\n") + 1)
        line_start = next_line
        line_end = line_start + line_count - 1
        chunks.append(
            Chunk(
                id=str(row["skill_id"]),
                index=int(row["chunk_index"] or 0),
                content=content,
                line_start=line_start,
                line_end=line_end,
            )
        )
        text_so_far += content
        next_line = line_end + 1
    return chunks


def _non_overlapping_suffix(current_text: str, next_chunk: str) -> str:
    if not current_text:
        return next_chunk
    if not next_chunk:
        return ""

    scan_len = min(len(current_text), len(next_chunk), 4000)
    current_tail = current_text[-scan_len:]
    for overlap_len in range(scan_len, 0, -1):
        if current_tail[-overlap_len:] == next_chunk[:overlap_len]:
            return next_chunk[overlap_len:]
    if next_chunk in current_tail:
        return ""
    return f"\n\n{next_chunk}"
