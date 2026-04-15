"""
Session store: maps (user_id, chat_id) → worktree session metadata,
               and env_slug → persistent environment container metadata.

Uses Redis as primary fast cache (with TTL for auto-expiry) and
PostgreSQL as persistent record for audit / restart recovery.

Environments are now GLOBAL (keyed by env_slug, not user_id).
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Optional

import asyncpg
import redis.asyncio as aioredis

log = logging.getLogger(__name__)


@dataclass
class EnvironmentRecord:
    """Represents a running environment container for a global env slug."""

    env_slug: str
    container_id: str
    container_ip: str
    status: str = "running"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "EnvironmentRecord":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class SandboxRecord:
    """Represents a live worktree session for a (user_id, chat_id) pair."""

    user_id: str
    chat_id: str
    env_slug: str
    container_id: str
    container_ip: str
    grpc_port: int
    worktree_path: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SandboxRecord":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


_SCHEMA = """
CREATE TABLE IF NOT EXISTS cappy_env_containers (
    id           SERIAL PRIMARY KEY,
    env_slug     TEXT NOT NULL UNIQUE,
    container_id TEXT NOT NULL,
    container_ip TEXT NOT NULL,
    status       TEXT DEFAULT 'running',
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    last_active  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cappy_sessions (
    id             SERIAL PRIMARY KEY,
    user_id        TEXT NOT NULL,
    chat_id        TEXT NOT NULL,
    env_slug       TEXT NOT NULL DEFAULT 'default',
    container_id   TEXT,
    container_ip   TEXT,
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
ALTER TABLE cappy_env_containers DROP COLUMN IF EXISTS repo_url;
ALTER TABLE cappy_env_containers DROP COLUMN IF EXISTS branch;
ALTER TABLE cappy_sessions DROP COLUMN IF EXISTS repo_url;
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
    def _env_key(env_slug: str) -> str:
        return f"env:{env_slug}"

    @staticmethod
    def _session_key(user_id: str, chat_id: str) -> str:
        return f"sandbox:{user_id}:{chat_id}"

    # ── Repository config lookup ─────────────────────────────────

    async def get_repo_config(self, env_slug: str) -> tuple[str, str] | None:
        """Look up repo_url and branch for an env_slug from the canonical repo_environments table.

        Returns (repo_url, branch) or None if env_slug has no matching record.
        Not cached in Redis — called only at container-creation time (infrequent path).
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT repo_url, branch FROM repo_environments WHERE slug = $1",
                env_slug,
            )
        if row:
            return row["repo_url"], row["branch"]
        return None

    # ── Environment CRUD ─────────────────────────────────────────

    async def get_env(self, env_slug: str) -> Optional[EnvironmentRecord]:
        """Return environment record from Redis cache, or fall back to PostgreSQL."""
        key = self._env_key(env_slug)

        raw = await self._redis.get(key)
        if raw:
            return EnvironmentRecord.from_dict(json.loads(raw))

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM cappy_env_containers WHERE env_slug=$1",
                env_slug,
            )
        if row:
            record = EnvironmentRecord.from_dict(dict(row))
            await self._redis.set(key, json.dumps(record.to_dict()))
            return record

        return None

    async def save_env(self, record: EnvironmentRecord) -> None:
        """Persist environment record to Redis and PostgreSQL."""
        key = self._env_key(record.env_slug)
        await self._redis.set(key, json.dumps(record.to_dict()))

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO cappy_env_containers
                    (env_slug, container_id, container_ip, status)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (env_slug) DO UPDATE
                    SET container_id = EXCLUDED.container_id,
                        container_ip = EXCLUDED.container_ip,
                        status       = EXCLUDED.status,
                        last_active  = NOW()
                """,
                record.env_slug,
                record.container_id,
                record.container_ip,
                record.status,
            )

    async def delete_env(self, env_slug: str) -> None:
        """Remove environment record from both stores."""
        await self._redis.delete(self._env_key(env_slug))
        async with self._pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM cappy_env_containers WHERE env_slug=$1",
                env_slug,
            )

    async def update_env_status(self, env_slug: str, status: str) -> None:
        """Update environment status in Redis and PostgreSQL."""
        key = self._env_key(env_slug)
        raw = await self._redis.get(key)
        if raw:
            data = json.loads(raw)
            data["status"] = status
            await self._redis.set(key, json.dumps(data))
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE cappy_env_containers SET status=$1, last_active=NOW() WHERE env_slug=$2",
                status,
                env_slug,
            )

    async def update_env_ip(self, env_slug: str, container_ip: str) -> None:
        """Update container IP after a restart (Redis + PostgreSQL)."""
        key = self._env_key(env_slug)
        raw = await self._redis.get(key)
        if raw:
            data = json.loads(raw)
            data["container_ip"] = container_ip
            await self._redis.set(key, json.dumps(data))
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE cappy_env_containers SET container_ip=$1, last_active=NOW() WHERE env_slug=$2",
                container_ip,
                env_slug,
            )

    async def list_idle_environments(self, env_idle_ttl: int) -> list[dict]:
        """Return environment DB rows idle longer than env_idle_ttl seconds and still 'running'."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT env_slug, container_id
                FROM   cappy_env_containers
                WHERE  status = 'running'
                  AND  last_active < NOW() - make_interval(secs => $1)
                """,
                float(env_idle_ttl),
            )
        return [dict(r) for r in rows]

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
                    (user_id, chat_id, env_slug, container_id, container_ip,
                     grpc_port, worktree_path)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (user_id, chat_id) DO UPDATE
                    SET env_slug      = EXCLUDED.env_slug,
                        container_id  = EXCLUDED.container_id,
                        container_ip  = EXCLUDED.container_ip,
                        grpc_port     = EXCLUDED.grpc_port,
                        worktree_path = EXCLUDED.worktree_path,
                        last_active   = NOW()
                """,
                record.user_id,
                record.chat_id,
                record.env_slug,
                record.container_id,
                record.container_ip,
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

    async def list_sessions_for_env(self, env_slug: str) -> list[dict]:
        """Return all active sessions for a given environment slug."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT user_id, chat_id, worktree_path FROM cappy_sessions WHERE env_slug=$1",
                env_slug,
            )
        return [dict(r) for r in rows]
