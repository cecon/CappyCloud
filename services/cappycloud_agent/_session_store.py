"""
Session store: maps (user_id, chat_id) → worktree session metadata.

Redis — cache rápido com TTL para auto-expirar sessões ociosas.
PostgreSQL — registro persistente para recovery após restart.

SandboxRecord agora suporta sessões multi-repo:
  - repos: lista de {slug, alias, base_branch, branch_name, worktree_path}
  - session_root: /repos/sessions/<session_id>/  (working_directory do openclaude)
  - sandbox_id: UUID do sandbox alocado para esta sessão
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
class SandboxRecord:
    """Sessão ativa de worktree para um (user_id, chat_id)."""

    user_id: str
    chat_id: str
    grpc_host: str
    grpc_port: int
    repos: list[dict] = field(default_factory=list)
    session_root: str = ""
    sandbox_id: str = ""
    sandbox_name: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SandboxRecord":
        d = dict(data)
        # Backward compat: container_ip → grpc_host
        if "container_ip" in d and "grpc_host" not in d:
            d["grpc_host"] = d.pop("container_ip")
        # Backward compat: worktree_path → session_root para registros antigos
        if not d.get("session_root") and d.get("worktree_path"):
            d["session_root"] = d["worktree_path"]
        d.setdefault("repos", [])
        d.setdefault("session_root", "")
        d.setdefault("sandbox_id", "")
        d.setdefault("sandbox_name", "")
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    @property
    def working_directory(self) -> str:
        """Diretório de trabalho que o openclaude deve usar."""
        if len(self.repos) == 1:
            repo = self.repos[0]
            worktree_path = repo.get("worktree_path")
            if worktree_path:
                return worktree_path
            alias = repo.get("alias") or repo.get("slug")
            if self.session_root and alias:
                return f"{self.session_root.rstrip('/')}/{alias}"
        return self.session_root or "/repos/default"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS cappy_sessions (
    id             SERIAL PRIMARY KEY,
    user_id        TEXT NOT NULL,
    chat_id        TEXT NOT NULL,
    sandbox_id     TEXT NOT NULL DEFAULT '',
    sandbox_name   TEXT NOT NULL DEFAULT '',
    grpc_host      TEXT,
    grpc_port      INTEGER,
    session_root   TEXT NOT NULL DEFAULT '',
    repos          JSONB NOT NULL DEFAULT '[]',
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    last_active    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, chat_id)
);
"""

_MIGRATE = """
ALTER TABLE cappy_sessions ADD COLUMN IF NOT EXISTS sandbox_id   TEXT NOT NULL DEFAULT '';
ALTER TABLE cappy_sessions ADD COLUMN IF NOT EXISTS sandbox_name TEXT NOT NULL DEFAULT '';
ALTER TABLE cappy_sessions ADD COLUMN IF NOT EXISTS session_root TEXT NOT NULL DEFAULT '';
ALTER TABLE cappy_sessions ADD COLUMN IF NOT EXISTS repos        JSONB NOT NULL DEFAULT '[]';
ALTER TABLE cappy_sessions ADD COLUMN IF NOT EXISTS grpc_host    TEXT;
ALTER TABLE cappy_sessions DROP COLUMN IF EXISTS repo_url;
ALTER TABLE cappy_sessions DROP COLUMN IF EXISTS env_slug;
ALTER TABLE cappy_sessions DROP COLUMN IF EXISTS container_id;
ALTER TABLE cappy_sessions DROP COLUMN IF EXISTS worktree_path;
DROP TABLE IF EXISTS cappy_env_containers;
"""


class SessionStore:
    def __init__(self, redis_url: str, database_url: str, idle_ttl: int = 1800) -> None:
        self._redis_url = redis_url
        self._db_url = database_url
        self._idle_ttl = idle_ttl
        self._redis: Optional[aioredis.Redis] = None
        self._pool: Optional[asyncpg.Pool] = None

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

    @staticmethod
    def _key(user_id: str, chat_id: str) -> str:
        return f"sandbox:{user_id}:{chat_id}"

    async def get(self, user_id: str, chat_id: str) -> Optional[SandboxRecord]:
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
            await self._redis.setex(key, self._idle_ttl, json.dumps(record.to_dict()))
            return record
        return None

    async def save(self, record: SandboxRecord) -> None:
        key = self._key(record.user_id, record.chat_id)
        await self._redis.setex(key, self._idle_ttl, json.dumps(record.to_dict()))

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO cappy_sessions
                    (user_id, chat_id, sandbox_id, sandbox_name,
                     grpc_host, grpc_port, session_root, repos)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
                ON CONFLICT (user_id, chat_id) DO UPDATE
                    SET sandbox_id   = EXCLUDED.sandbox_id,
                        sandbox_name = EXCLUDED.sandbox_name,
                        grpc_host    = EXCLUDED.grpc_host,
                        grpc_port    = EXCLUDED.grpc_port,
                        session_root = EXCLUDED.session_root,
                        repos        = EXCLUDED.repos,
                        last_active  = NOW()
                """,
                record.user_id,
                record.chat_id,
                record.sandbox_id,
                record.sandbox_name,
                record.grpc_host,
                record.grpc_port,
                record.session_root,
                json.dumps(record.repos),
            )

    async def refresh_ttl(self, user_id: str, chat_id: str) -> None:
        key = self._key(user_id, chat_id)
        await self._redis.expire(key, self._idle_ttl)
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE cappy_sessions SET last_active=NOW() WHERE user_id=$1 AND chat_id=$2",
                user_id,
                chat_id,
            )

    async def delete(self, user_id: str, chat_id: str) -> None:
        key = self._key(user_id, chat_id)
        await self._redis.delete(key)
        async with self._pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM cappy_sessions WHERE user_id=$1 AND chat_id=$2",
                user_id,
                chat_id,
            )

    async def list_expired_sessions(self) -> list[dict]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT user_id, chat_id, sandbox_id, session_root, repos
                FROM   cappy_sessions
                WHERE  last_active < NOW() - make_interval(secs => $1)
                """,
                float(self._idle_ttl),
            )
        return [dict(r) for r in rows]
