"""
Session store: maps (user_id, chat_id) → worktree session metadata.

Uses Redis as primary fast cache (with TTL for auto-expiry) and
PostgreSQL as persistent record for audit / restart recovery.

The environment is now a single fixed service (cappycloud-sandbox).
This store only manages per-conversation worktree sessions.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from typing import Optional

import asyncpg
import redis.asyncio as aioredis

log = logging.getLogger(__name__)


@dataclass
class SandboxRecord:
    """Represents a live worktree session for a (user_id, chat_id) pair."""

    user_id: str
    chat_id: str
    env_slug: str
    container_id: str
    grpc_host: str
    grpc_port: int
    worktree_path: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SandboxRecord":
        # Suporte a registros antigos com campo container_ip
        if "container_ip" in data and "grpc_host" not in data:
            data = dict(data)
            data["grpc_host"] = data.pop("container_ip")
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


_SCHEMA = """
CREATE TABLE IF NOT EXISTS cappy_sessions (
    id             SERIAL PRIMARY KEY,
    user_id        TEXT NOT NULL,
    chat_id        TEXT NOT NULL,
    env_slug       TEXT NOT NULL DEFAULT 'default',
    container_id   TEXT,
    grpc_host      TEXT,
    grpc_port      INTEGER,
    worktree_path  TEXT DEFAULT '',
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    last_active    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, chat_id)
);
"""

_MIGRATE = """
ALTER TABLE cappy_sessions ADD COLUMN IF NOT EXISTS worktree_path TEXT DEFAULT '';
ALTER TABLE cappy_sessions ADD COLUMN IF NOT EXISTS env_slug TEXT DEFAULT 'default';
ALTER TABLE cappy_sessions ADD COLUMN IF NOT EXISTS grpc_host TEXT;
ALTER TABLE cappy_sessions DROP COLUMN IF EXISTS repo_url;
DROP TABLE IF EXISTS cappy_env_containers;
"""


class SessionStore:
    def __init__(self, redis_url: str, database_url: str, idle_ttl: int = 1800) -> None:
        self._redis_url = redis_url
        self._db_url = database_url
        self._idle_ttl = idle_ttl
        self._redis: Optional[aioredis.Redis] = None
        self._pool: Optional[asyncpg.Pool] = None

    # ── Lifecycle ────────────────────────────────────────────────

    async def connect(self) -> None:
        self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
        self._pool = await asyncpg.create_pool(self._db_url, min_size=1, max_size=5)
        async with self._pool.acquire() as conn:
            await conn.execute(_SCHEMA)
            await conn.execute(_MIGRATE)
        log.info("SessionStore connected (redis=%s)", self._redis_url)

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()
        if self._pool:
            await self._pool.close()

    # ── Redis key helpers ────────────────────────────────────────

    @staticmethod
    def _session_key(user_id: str, chat_id: str) -> str:
        return f"sandbox:{user_id}:{chat_id}"

    # ── Session CRUD ─────────────────────────────────────────────

    async def get(self, user_id: str, chat_id: str) -> Optional[SandboxRecord]:
        """Return session record from Redis cache, or fall back to PostgreSQL."""
        key = self._session_key(user_id, chat_id)

        raw = await self._redis.get(key)
        if raw:
            return SandboxRecord.from_dict(json.loads(raw))

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM cappy_sessions WHERE user_id=$1 AND chat_id=$2",
                user_id,
                chat_id,
            )
        if row:
            record = SandboxRecord.from_dict(dict(row))
            await self._redis.setex(key, self._idle_ttl, json.dumps(record.to_dict()))
            return record

        return None

    async def save(self, record: SandboxRecord) -> None:
        """Persist session record to Redis (with TTL) and PostgreSQL."""
        key = self._session_key(record.user_id, record.chat_id)
        await self._redis.setex(key, self._idle_ttl, json.dumps(record.to_dict()))

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO cappy_sessions
                    (user_id, chat_id, env_slug, container_id, grpc_host,
                     grpc_port, worktree_path)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (user_id, chat_id) DO UPDATE
                    SET env_slug      = EXCLUDED.env_slug,
                        container_id  = EXCLUDED.container_id,
                        grpc_host     = EXCLUDED.grpc_host,
                        grpc_port     = EXCLUDED.grpc_port,
                        worktree_path = EXCLUDED.worktree_path,
                        last_active   = NOW()
                """,
                record.user_id,
                record.chat_id,
                record.env_slug,
                record.container_id,
                record.grpc_host,
                record.grpc_port,
                record.worktree_path,
            )

    async def refresh_ttl(self, user_id: str, chat_id: str) -> None:
        """Reset idle TTL so the session stays alive after activity."""
        key = self._session_key(user_id, chat_id)
        await self._redis.expire(key, self._idle_ttl)
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE cappy_sessions SET last_active=NOW() WHERE user_id=$1 AND chat_id=$2",
                user_id,
                chat_id,
            )

    async def delete(self, user_id: str, chat_id: str) -> None:
        """Remove session record from both stores."""
        key = self._session_key(user_id, chat_id)
        await self._redis.delete(key)
        async with self._pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM cappy_sessions WHERE user_id=$1 AND chat_id=$2",
                user_id,
                chat_id,
            )

    async def list_expired_sessions(self) -> list[dict]:
        """Return session DB rows whose idle TTL has expired."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT user_id, chat_id, container_id, worktree_path, env_slug
                FROM   cappy_sessions
                WHERE  last_active < NOW() - make_interval(secs => $1)
                """,
                float(self._idle_ttl),
            )
        return [dict(r) for r in rows]
