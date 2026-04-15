"""
Session store: maps (user_id, chat_id) → sandbox metadata.

Uses Redis as primary fast cache (with TTL for auto-expiry) and
PostgreSQL as persistent record for audit / restart recovery.
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
    """Represents a live sandbox container for a user session."""

    user_id: str
    chat_id: str
    container_id: str
    container_ip: str
    grpc_port: int
    workspace_repo: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SandboxRecord":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


_SCHEMA = """
CREATE TABLE IF NOT EXISTS cappy_sessions (
    id           SERIAL PRIMARY KEY,
    user_id      TEXT NOT NULL,
    chat_id      TEXT NOT NULL,
    container_id TEXT,
    container_ip TEXT,
    grpc_port    INTEGER,
    workspace_repo TEXT DEFAULT '',
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    last_active  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, chat_id)
);
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
        log.info("SessionStore connected (redis=%s)", self._redis_url)

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()
        if self._pool:
            await self._pool.close()

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _key(user_id: str, chat_id: str) -> str:
        return f"sandbox:{user_id}:{chat_id}"

    # ── CRUD ─────────────────────────────────────────────────────

    async def get(self, user_id: str, chat_id: str) -> Optional[SandboxRecord]:
        """Return sandbox record from Redis cache, or fall back to PostgreSQL."""
        key = self._key(user_id, chat_id)

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
            # Re-hydrate Redis cache
            await self._redis.setex(key, self._idle_ttl, json.dumps(record.to_dict()))
            return record

        return None

    async def save(self, record: SandboxRecord) -> None:
        """Persist sandbox record to Redis (with TTL) and PostgreSQL."""
        key = self._key(record.user_id, record.chat_id)
        await self._redis.setex(key, self._idle_ttl, json.dumps(record.to_dict()))

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO cappy_sessions
                    (user_id, chat_id, container_id, container_ip, grpc_port, workspace_repo)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (user_id, chat_id) DO UPDATE
                    SET container_id  = EXCLUDED.container_id,
                        container_ip  = EXCLUDED.container_ip,
                        grpc_port     = EXCLUDED.grpc_port,
                        workspace_repo = EXCLUDED.workspace_repo,
                        last_active   = NOW()
                """,
                record.user_id,
                record.chat_id,
                record.container_id,
                record.container_ip,
                record.grpc_port,
                record.workspace_repo,
            )

    async def refresh_ttl(self, user_id: str, chat_id: str) -> None:
        """Reset idle TTL so the sandbox stays alive after activity."""
        key = self._key(user_id, chat_id)
        await self._redis.expire(key, self._idle_ttl)
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE cappy_sessions SET last_active=NOW() WHERE user_id=$1 AND chat_id=$2",
                user_id,
                chat_id,
            )

    async def delete(self, user_id: str, chat_id: str) -> None:
        """Remove sandbox record from both stores."""
        key = self._key(user_id, chat_id)
        await self._redis.delete(key)
        async with self._pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM cappy_sessions WHERE user_id=$1 AND chat_id=$2",
                user_id,
                chat_id,
            )

    async def list_expired_containers(self) -> list[dict]:
        """Return DB rows whose Redis key has already expired (i.e., idle > TTL)."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT user_id, chat_id, container_id
                FROM   cappy_sessions
                WHERE  last_active < NOW() - make_interval(secs => $1)
                """,
                float(self._idle_ttl),
            )
        return [dict(r) for r in rows]
