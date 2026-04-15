"""
Persistência de chunks de código com pgvector.
Tabela: code_chunks (user_id, file_path, chunk_name, embedding, …)
"""
from __future__ import annotations

import logging
from typing import Optional

import asyncpg  # type: ignore
from pgvector.asyncpg import register_vector  # type: ignore

from .config import settings

log = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=10)
        async with _pool.acquire() as conn:
            await register_vector(conn)
            await _ensure_schema(conn)
    return _pool


async def _ensure_schema(conn: asyncpg.Connection) -> None:
    """Cria a tabela e os índices se ainda não existirem."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS code_chunks (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     TEXT NOT NULL,
            repo_url    TEXT NOT NULL,
            file_path   TEXT NOT NULL,
            language    TEXT NOT NULL,
            chunk_type  TEXT NOT NULL,
            chunk_name  TEXT,
            start_line  INT,
            end_line    INT,
            content     TEXT NOT NULL,
            embedding   vector(384),
            indexed_at  TIMESTAMPTZ DEFAULT NOW()
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS code_chunks_user_idx
            ON code_chunks (user_id);
    """)
    # IVFFlat índice para cosine similarity — criado só se não existir
    try:
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS code_chunks_embedding_idx
                ON code_chunks USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100);
        """)
    except Exception as exc:
        # Índice IVFFlat requer dados para ser criado; ignora erro na criação inicial
        log.debug("Índice IVFFlat adiado (tabela vazia?): %s", exc)


async def delete_user_chunks(user_id: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM code_chunks WHERE user_id = $1", user_id)


async def insert_chunks(rows: list[dict]) -> None:
    """
    Insere chunks em lote.
    Cada dict deve ter: user_id, repo_url, file_path, language, chunk_type,
                        chunk_name, start_line, end_line, content, embedding.
    """
    if not rows:
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        await register_vector(conn)
        await conn.executemany(
            """
            INSERT INTO code_chunks
                (user_id, repo_url, file_path, language, chunk_type,
                 chunk_name, start_line, end_line, content, embedding)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            """,
            [
                (
                    r["user_id"], r["repo_url"], r["file_path"], r["language"],
                    r["chunk_type"], r.get("chunk_name"), r.get("start_line"),
                    r.get("end_line"), r["content"], r["embedding"],
                )
                for r in rows
            ],
        )


async def semantic_search(
    user_id: str,
    query_embedding: list[float],
    limit: int = 10,
    language: Optional[str] = None,
) -> list[dict]:
    """Busca semântica por cosine similarity."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await register_vector(conn)

        lang_filter = "AND language = $4" if language else ""
        params: list = [user_id, query_embedding, limit]
        if language:
            params.append(language)

        rows = await conn.fetch(
            f"""
            SELECT file_path, language, chunk_type, chunk_name,
                   start_line, end_line, content,
                   1 - (embedding <=> $2) AS similarity
            FROM code_chunks
            WHERE user_id = $1 {lang_filter}
            ORDER BY embedding <=> $2
            LIMIT $3
            """,
            *params,
        )
        return [dict(r) for r in rows]
