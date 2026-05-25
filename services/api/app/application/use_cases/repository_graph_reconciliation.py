"""GraphRAG reconciliation materialization helpers."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.repository_graph_mapping import translate_sandbox_graph
from app.infrastructure.config import get_settings
from app.infrastructure.orm_models import (
    GraphEdge,
    GraphReconciliationRun,
    Repository,
    SandboxSyncQueue,
)

log = logging.getLogger(__name__)

LLM_GAP_SOURCE = "llm_gap"
LLM_RECONCILIATION_VERSION = "0.2.0"
RECONCILIATION_MODES = {"all", "strict-only", "no-llm"}
_INSERT_BATCH_SIZE = 1000


async def enqueue_graph_reconciliation(
    session: AsyncSession,
    *,
    repo: Repository,
    commit_sha: str,
    mode: str = "all",
    llm_model: str | None = None,
    priority: int = 5,
) -> uuid.UUID:
    if not repo.sandbox_id:
        raise ValueError("Repositório sem sandbox associado.")
    if mode not in RECONCILIATION_MODES:
        raise ValueError("mode inválido para reconciliação.")
    job_id = uuid.uuid4()
    payload: dict[str, Any] = {
        "repo_id": str(repo.id),
        "slug": repo.slug,
        "commit_sha": commit_sha,
        "mode": mode,
    }
    if llm_model:
        payload["llm_model"] = llm_model
    session.add(
        SandboxSyncQueue(
            id=job_id,
            sandbox_id=repo.sandbox_id,
            operation="reconcile_repo_graph",
            payload=payload,
            priority=priority,
        )
    )
    return job_id


async def reconcile_repo_graph(
    session: AsyncSession,
    *,
    repo: Repository,
    commit_sha: str,
    mode: str = "all",
    llm_model: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    payload = await fetch_reconciliation_graph(
        repo_id=repo.id,
        commit_sha=commit_sha,
        mode=mode,
        llm_model=llm_model,
        limit=limit,
    )
    graph = _graph_wrapper(repo, payload)
    rows = translate_sandbox_graph(repo_id=repo.id, commit_sha=commit_sha, graph=graph)
    edges_inserted = await _insert_edges(session, rows.edges)
    run = GraphReconciliationRun(
        id=uuid.uuid4(),
        repo_id=repo.id,
        commit_sha=commit_sha,
        extractor_version=str(payload.get("extractor_version") or LLM_RECONCILIATION_VERSION),
        llm_model=payload.get("llm_model"),
        mode=str(payload.get("mode") or mode),
        summary=dict(payload.get("summary") or {}),
        unresolved=[d for d in payload.get("diagnostics") or [] if isinstance(d, dict)],
    )
    session.add(run)
    log.info(
        "graph_reconciliation_complete %s",
        json.dumps({**run.summary, "edges_inserted": edges_inserted}, default=str),
    )
    return {"edges_inserted": edges_inserted, "run_id": str(run.id), "summary": run.summary}


async def fetch_reconciliation_graph(
    *,
    repo_id: uuid.UUID,
    commit_sha: str,
    mode: str = "all",
    llm_model: str | None = None,
    limit: int | None = None,
    db_url: str | None = None,
) -> dict[str, Any]:
    out_path = _temp_json_path()
    command = os.getenv("CAPPY_LLM_RECONCILIATION_EXTRACTOR", "cappy-llm-reconciliation")
    args = [
        command,
        "--repo-id",
        str(repo_id),
        "--commit-sha",
        commit_sha,
        "--out",
        str(out_path),
        "--db-url",
        db_url or get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://", 1),
        "--mode",
        mode,
    ]
    if llm_model:
        args.extend(["--llm-model", llm_model])
    if limit and limit > 0:
        args.extend(["--limit", str(limit)])
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60 * 30)
        if proc.returncode != 0:
            detail = (stderr or stdout).decode(errors="ignore")[-1200:]
            raise RuntimeError(f"llm_reconciliation failed: {detail}")
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError("llm_reconciliation returned invalid JSON payload")
        return payload
    finally:
        out_path.unlink(missing_ok=True)


async def latest_reconciliation_summary(
    session: AsyncSession,
    *,
    repo_id: uuid.UUID,
    commit_sha: str,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any] | None:
    row = await session.execute(
        select(GraphReconciliationRun)
        .where(GraphReconciliationRun.repo_id == repo_id)
        .where(GraphReconciliationRun.commit_sha == commit_sha)
        .order_by(desc(GraphReconciliationRun.created_at))
        .limit(1)
    )
    run = row.scalar_one_or_none()
    if run is None:
        return None
    unresolved = list(run.unresolved or [])
    return {
        "run_id": str(run.id),
        "repo_id": str(run.repo_id),
        "commit_sha": run.commit_sha,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "summary": run.summary or {},
        "unresolved_total": len(unresolved),
        "unresolved": unresolved[offset : offset + limit],
        "limit": limit,
        "offset": offset,
    }


async def find_resolution_edge(
    session: AsyncSession,
    *,
    repo_id: uuid.UUID,
    commit_sha: str,
    original_edge_key: str | None = None,
    edge_id: int | None = None,
) -> dict[str, Any] | None:
    key = original_edge_key
    if key is None and edge_id is not None:
        original = await session.get(GraphEdge, edge_id)
        if original is None:
            return None
        key = _original_edge_key(original)
    if not key:
        return None
    row = await session.execute(
        select(GraphEdge)
        .where(GraphEdge.repo_id == repo_id)
        .where(GraphEdge.commit_sha == commit_sha)
        .where(GraphEdge.source_extractor == LLM_GAP_SOURCE)
        .where(GraphEdge.type == "resolves_to")
        .where(GraphEdge.evidence["attrs"]["original_edge_key"].astext == key)
        .limit(1)
    )
    edge = row.scalar_one_or_none()
    return _edge_dict(edge) if edge else None


def _graph_wrapper(repo: Repository, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "slug": repo.slug,
        "repo_path": repo.sandbox_path,
        "generated_at": "",
        "stats": {"symbols": 0, "flows": len(payload.get("edges") or [])},
        "nodes": [],
        "edges": [],
        "files": [],
        "symbols": [],
        "file_edges": [],
        "semantic_nodes": [],
        "semantic_edges": payload.get("edges") or [],
        "findings": [],
    }


async def _insert_edges(session: AsyncSession, rows: list[Any]) -> int:
    if not rows:
        return 0
    inserted = 0
    for index in range(0, len(rows), _INSERT_BATCH_SIZE):
        batch = rows[index : index + _INSERT_BATCH_SIZE]
        result = await session.execute(
            pg_insert(GraphEdge).values([row.__dict__ for row in batch]).on_conflict_do_nothing()
        )
        inserted += max(0, int(getattr(result, "rowcount", 0) or 0))
    return inserted


def _edge_dict(edge: GraphEdge) -> dict[str, Any]:
    return {
        "id": edge.id,
        "source_id": edge.source_id,
        "target_id": edge.target_id,
        "target_external": edge.target_external,
        "type": edge.type,
        "confidence": edge.confidence,
        "source_extractor": edge.source_extractor,
        "extractor_version": edge.extractor_version,
        "evidence": edge.evidence,
    }


def _original_edge_key(edge: GraphEdge) -> str:
    raw = (
        f"{edge.repo_id}:{edge.commit_sha}:{edge.source_id}:"
        f"{edge.target_external or ''}:{edge.type}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _temp_json_path() -> Path:
    with tempfile.NamedTemporaryFile(
        prefix="cappy-llm-reconciliation-",
        suffix=".json",
        delete=False,
    ) as handle:
        return Path(handle.name)
