"""Materialize sandbox repository graphs into Postgres."""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, desc, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.secondary.sandbox_repo_graph_provider import (
    SandboxRepoGraphError,
    SandboxRepositoryGraphProvider,
)
from app.application.use_cases.repository_graph_doc_import import (
    append_doc_import_graph,
    fetch_doc_import_graph,
    list_doc_import_document_ids,
)
from app.application.use_cases.repository_graph_mapping import (
    EXTRACTOR_VERSION,
    GraphEdgeInsert,
    GraphNodeInsert,
    translate_sandbox_graph,
)
from app.application.use_cases.repository_graph_reconstruction import reconstruct_graph_from_rows
from app.infrastructure.orm_models import (
    GraphEdge,
    GraphNode,
    Repository,
    Sandbox,
    SandboxSyncQueue,
)

log = logging.getLogger(__name__)
_INSERT_BATCH_SIZE = 1000


@dataclass(frozen=True)
class GraphMaterializationResult:
    repo_id: uuid.UUID
    commit_sha: str
    nodes_inserted: int
    edges_inserted: int
    duration_ms: int
    extractor_version: str


async def materialize_repo_graph(
    session: AsyncSession,
    *,
    repo: Repository,
    commit_sha: str,
    max_files: int = 1200,
    provider: SandboxRepositoryGraphProvider | None = None,
) -> GraphMaterializationResult:
    """Fetch the current sandbox graph and insert deterministic rows idempotently."""
    if repo.sandbox_id is None:
        raise ValueError("Repositório sem sandbox associado.")
    sandbox = await session.get(Sandbox, repo.sandbox_id)
    if sandbox is None:
        raise ValueError("Sandbox do repositório não encontrado.")

    started = time.perf_counter()
    graph_provider = provider or SandboxRepositoryGraphProvider()
    graph = await graph_provider.fetch_graph(
        sandbox_host=sandbox.host,
        sandbox_port=sandbox.session_port,
        slug=repo.slug,
        max_files=max_files,
    )
    doc_ids = await list_doc_import_document_ids(session, repo.id)
    if doc_ids:
        doc_graph = await fetch_doc_import_graph(
            repo_id=repo.id,
            commit_sha=commit_sha,
            document_ids=doc_ids,
        )
        append_doc_import_graph(graph, doc_graph)
    rows = translate_sandbox_graph(repo_id=repo.id, commit_sha=commit_sha, graph=graph)
    _warn_cross_extractor_edge_collisions(rows.edges)
    nodes_inserted = await _insert_nodes(session, rows.nodes)
    edges_inserted = await _insert_edges(session, rows.edges)
    duration_ms = int((time.perf_counter() - started) * 1000)
    result = GraphMaterializationResult(
        repo_id=repo.id,
        commit_sha=commit_sha,
        nodes_inserted=nodes_inserted,
        edges_inserted=edges_inserted,
        duration_ms=duration_ms,
        extractor_version=EXTRACTOR_VERSION,
    )
    log.info("graph_materialization_complete %s", json.dumps(result.__dict__, default=str))
    return result


async def resolve_repo_graph_commit_sha(
    *,
    provider: SandboxRepositoryGraphProvider,
    repo: Repository,
    sandbox: Sandbox,
) -> str:
    """Resolve the graph commit, trying the configured default branch before HEAD."""
    refs = [ref for ref in [repo.default_branch, "HEAD"] if ref]
    seen: set[str] = set()
    last_error: SandboxRepoGraphError | None = None
    for ref in refs:
        if ref in seen:
            continue
        seen.add(ref)
        try:
            return await provider.fetch_commit_sha(
                sandbox_host=sandbox.host,
                sandbox_port=sandbox.session_port,
                slug=repo.slug,
                ref=ref,
            )
        except SandboxRepoGraphError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise SandboxRepoGraphError("Não foi possível resolver HEAD do repositório.", status_code=409)


async def load_materialized_repo_graph(
    session: AsyncSession,
    *,
    repo: Repository,
    commit_sha: str,
) -> dict[str, Any] | None:
    node_rows = (
        (
            await session.execute(
                select(GraphNode)
                .where(GraphNode.repo_id == repo.id, GraphNode.commit_sha == commit_sha)
                .order_by(GraphNode.id)
            )
        )
        .scalars()
        .all()
    )
    if not node_rows:
        return None
    edge_rows = (
        (
            await session.execute(
                select(GraphEdge)
                .where(GraphEdge.repo_id == repo.id, GraphEdge.commit_sha == commit_sha)
                .order_by(
                    GraphEdge.type,
                    GraphEdge.source_id,
                    GraphEdge.target_id,
                    GraphEdge.target_external,
                )
            )
        )
        .scalars()
        .all()
    )
    return reconstruct_graph_from_rows(
        repo_slug=repo.slug,
        repo_path=repo.sandbox_path,
        nodes=list(node_rows),
        edges=list(edge_rows),
    )


async def latest_materialized_commit_sha(
    session: AsyncSession,
    repo_id: uuid.UUID,
) -> str | None:
    row = await session.execute(
        select(GraphNode.commit_sha)
        .where(GraphNode.repo_id == repo_id)
        .order_by(desc(GraphNode.created_at))
        .limit(1)
    )
    first = row.first()
    return str(first[0]) if first else None


async def enqueue_graph_materialization(
    session: AsyncSession,
    *,
    repo: Repository,
    commit_sha: str,
    max_files: int = 1200,
    priority: int = 4,
) -> uuid.UUID:
    if not repo.sandbox_id:
        raise ValueError("Repositório sem sandbox associado.")
    job_id = uuid.uuid4()
    session.add(
        SandboxSyncQueue(
            id=job_id,
            sandbox_id=repo.sandbox_id,
            operation="materialize_repo_graph",
            payload={
                "repo_id": str(repo.id),
                "slug": repo.slug,
                "commit_sha": commit_sha,
                "max_files": max_files,
            },
            priority=priority,
        )
    )
    return job_id


async def invalidate_extractor(
    session: AsyncSession,
    *,
    repo_id: uuid.UUID,
    commit_sha: str,
    source_extractor: str,
) -> dict[str, int]:
    """Delete one extractor slice for a materialized repo graph commit."""
    edge_result = await session.execute(
        delete(GraphEdge).where(
            GraphEdge.repo_id == repo_id,
            GraphEdge.commit_sha == commit_sha,
            GraphEdge.source_extractor == source_extractor,
        )
    )
    node_result = await session.execute(
        delete(GraphNode).where(
            GraphNode.repo_id == repo_id,
            GraphNode.commit_sha == commit_sha,
            GraphNode.source_extractor == source_extractor,
        )
    )
    return {
        "edges_deleted": _rowcount(edge_result),
        "nodes_deleted": _rowcount(node_result),
    }


async def _insert_nodes(session: AsyncSession, rows: list[GraphNodeInsert]) -> int:
    if not rows:
        return 0
    inserted = 0
    for batch in _batched(rows, _INSERT_BATCH_SIZE):
        values = [row.__dict__ for row in batch]
        result = await session.execute(
            pg_insert(GraphNode)
            .values(values)
            .on_conflict_do_nothing(index_elements=[GraphNode.id])
        )
        inserted += _rowcount(result)
    return inserted


async def _insert_edges(session: AsyncSession, rows: list[GraphEdgeInsert]) -> int:
    if not rows:
        return 0
    inserted = 0
    for batch in _batched(rows, _INSERT_BATCH_SIZE):
        values = [row.__dict__ for row in batch]
        result = await session.execute(pg_insert(GraphEdge).values(values).on_conflict_do_nothing())
        inserted += _rowcount(result)
    return inserted


def _batched(rows: list[Any], size: int) -> Iterator[list[Any]]:
    for index in range(0, len(rows), size):
        yield rows[index : index + size]


def _rowcount(result: Any) -> int:
    return max(0, int(getattr(result, "rowcount", 0) or 0))


def _warn_cross_extractor_edge_collisions(rows: list[GraphEdgeInsert]) -> None:
    seen: dict[tuple[str, str, str, str], str] = {}
    for row in rows:
        target = row.target_id or row.target_external or ""
        key = (str(row.repo_id), row.commit_sha, row.source_id, f"{target}:{row.type}")
        previous = seen.get(key)
        if previous is not None and previous != row.source_extractor:
            log.warning(
                "graph_edge_cross_extractor_collision repo_id=%s commit_sha=%s "
                "source_id=%s target=%s type=%s extractors=%s,%s",
                row.repo_id,
                row.commit_sha,
                row.source_id,
                target,
                row.type,
                previous,
                row.source_extractor,
            )
        seen[key] = row.source_extractor
