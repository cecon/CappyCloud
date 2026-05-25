"""Doc-import graph extraction and materialization helpers."""

from __future__ import annotations

import asyncio
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

from app.adapters.secondary.sandbox_repo_graph_provider import (
    SandboxRepoGraphError,
    SandboxRepositoryGraphProvider,
)
from app.application.use_cases.repository_graph_mapping import translate_sandbox_graph
from app.infrastructure.config import get_settings
from app.infrastructure.orm_models import (
    Document,
    GraphEdge,
    GraphNode,
    Repository,
    Sandbox,
    SandboxSyncQueue,
)

log = logging.getLogger(__name__)

DOC_IMPORT_SOURCE = "doc_import"
SUPPORTED_DOC_IMPORT_SOURCE_TYPES = {"markdown"}
_INSERT_BATCH_SIZE = 1000


async def list_doc_import_document_ids(
    session: AsyncSession,
    repo_id: uuid.UUID,
    document_ids: list[uuid.UUID] | None = None,
) -> list[uuid.UUID]:
    stmt = (
        select(Document.id)
        .where(Document.repository_id == repo_id)
        .where(Document.status == "indexed")
        .where(Document.source_type.in_(SUPPORTED_DOC_IMPORT_SOURCE_TYPES))
    )
    if document_ids:
        stmt = stmt.where(Document.id.in_(document_ids))
    rows = await session.execute(stmt.order_by(Document.created_at))
    return list(rows.scalars())


async def fetch_doc_import_graph(
    *,
    repo_id: uuid.UUID,
    commit_sha: str,
    document_ids: list[uuid.UUID] | None = None,
    db_url: str | None = None,
) -> dict[str, Any]:
    out_path = _temp_json_path()
    command = os.getenv("CAPPY_DOC_IMPORT_EXTRACTOR", "cappy-doc-import-extractor")
    args = [
        command,
        "--repo-id",
        str(repo_id),
        "--commit-sha",
        commit_sha,
        "--out",
        str(out_path),
        "--db-url",
        db_url or get_settings().database_url,
    ]
    if document_ids:
        args.extend(["--document-ids", ",".join(str(item) for item in document_ids)])
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=90)
        if proc.returncode != 0:
            detail = (stderr or stdout).decode(errors="ignore")[-1000:]
            raise RuntimeError(f"doc_import extractor failed: {detail}")
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError("doc_import extractor returned invalid JSON payload")
        return payload
    finally:
        out_path.unlink(missing_ok=True)


def append_doc_import_graph(base_graph: dict[str, Any], doc_graph: dict[str, Any]) -> None:
    nodes = [item for item in doc_graph.get("nodes") or [] if isinstance(item, dict)]
    edges = [item for item in doc_graph.get("edges") or [] if isinstance(item, dict)]
    if not nodes and not edges:
        return
    base_graph.setdefault("semantic_nodes", []).extend(nodes)
    base_graph.setdefault("semantic_edges", []).extend(edges)
    base_graph.setdefault("findings", []).extend(_diagnostic_findings(doc_graph))
    stats = base_graph.setdefault("stats", {})
    stats["symbols"] = int(stats.get("symbols") or 0) + len(nodes)
    stats["flows"] = int(stats.get("flows") or 0) + len(edges)


async def materialize_doc_import(
    session: AsyncSession,
    *,
    repo: Repository,
    commit_sha: str,
    document_ids: list[uuid.UUID] | None = None,
) -> dict[str, int]:
    scoped_document_ids = await list_doc_import_document_ids(session, repo.id, document_ids)
    if not scoped_document_ids:
        return {"nodes_inserted": 0, "edges_inserted": 0}
    doc_graph = await fetch_doc_import_graph(
        repo_id=repo.id,
        commit_sha=commit_sha,
        document_ids=scoped_document_ids,
    )
    graph = _graph_wrapper(repo, doc_graph)
    rows = translate_sandbox_graph(repo_id=repo.id, commit_sha=commit_sha, graph=graph)
    nodes_inserted = await _insert_nodes(session, rows.nodes)
    edges_inserted = await _insert_edges(session, rows.edges)
    return {"nodes_inserted": nodes_inserted, "edges_inserted": edges_inserted}


async def enqueue_doc_import_for_document(
    session: AsyncSession,
    *,
    repo: Repository,
    document: Document,
    commit_sha: str | None = None,
    priority: int = 4,
) -> uuid.UUID | None:
    if (
        document.status != "indexed"
        or document.source_type not in SUPPORTED_DOC_IMPORT_SOURCE_TYPES
    ):
        return None
    if not repo.sandbox_id:
        log.info("doc_import skipped for document %s: repository has no sandbox", document.id)
        return None
    job_id = uuid.uuid4()
    payload: dict[str, Any] = {
        "repo_id": str(repo.id),
        "document_id": str(document.id),
        "slug": repo.slug,
    }
    if commit_sha:
        payload["commit_sha"] = commit_sha
    session.add(
        SandboxSyncQueue(
            id=job_id,
            sandbox_id=repo.sandbox_id,
            operation="doc_import_for_document",
            payload=payload,
            priority=priority,
        )
    )
    return job_id


async def resolve_doc_import_commit_sha(
    *,
    session: AsyncSession,
    repo: Repository,
    sandbox: Sandbox,
    provider: SandboxRepositoryGraphProvider | None = None,
) -> str:
    latest = await _latest_materialized_commit_sha(session, repo.id)
    if latest:
        return latest
    graph_provider = provider or SandboxRepositoryGraphProvider()
    refs = [ref for ref in [repo.default_branch, "HEAD"] if ref]
    last_error: SandboxRepoGraphError | None = None
    for ref in dict.fromkeys(refs):
        try:
            return await graph_provider.fetch_commit_sha(
                sandbox_host=sandbox.host,
                sandbox_port=sandbox.session_port,
                slug=repo.slug,
                ref=ref,
            )
        except SandboxRepoGraphError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise SandboxRepoGraphError(
        "Não foi possível resolver commit para doc_import.", status_code=409
    )


def _graph_wrapper(repo: Repository, doc_graph: dict[str, Any]) -> dict[str, Any]:
    return {
        "slug": repo.slug,
        "repo_path": repo.sandbox_path,
        "generated_at": "",
        "stats": {
            "symbols": len(doc_graph.get("nodes") or []),
            "flows": len(doc_graph.get("edges") or []),
        },
        "nodes": [],
        "edges": [],
        "files": [],
        "symbols": [],
        "file_edges": [],
        "semantic_nodes": doc_graph.get("nodes") or [],
        "semantic_edges": doc_graph.get("edges") or [],
        "findings": _diagnostic_findings(doc_graph),
    }


def _diagnostic_findings(doc_graph: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    for index, diagnostic in enumerate(doc_graph.get("diagnostics") or []):
        if not isinstance(diagnostic, dict):
            continue
        findings.append(
            {
                "id": (
                    f"doc_import:{index}:{diagnostic.get('document_id')}:{diagnostic.get('line')}"
                ),
                "type": "doc_import_diagnostic",
                "severity": "low",
                "level": diagnostic.get("level") or "info",
                "source": "doc_import",
                "title": diagnostic.get("code") or "doc_import",
                "detail": diagnostic.get("message") or "",
                "node_id": "",
                "path": str(diagnostic.get("document_id") or ""),
            }
        )
    return findings


async def _latest_materialized_commit_sha(session: AsyncSession, repo_id: uuid.UUID) -> str | None:
    row = await session.execute(
        select(GraphNode.commit_sha)
        .where(GraphNode.repo_id == repo_id)
        .order_by(desc(GraphNode.created_at))
        .limit(1)
    )
    first = row.first()
    return str(first[0]) if first else None


async def _insert_nodes(session: AsyncSession, rows: list[Any]) -> int:
    if not rows:
        return 0
    inserted = 0
    for batch in _batched(rows, _INSERT_BATCH_SIZE):
        result = await session.execute(
            pg_insert(GraphNode)
            .values([row.__dict__ for row in batch])
            .on_conflict_do_nothing(index_elements=[GraphNode.id])
        )
        inserted += _rowcount(result)
    return inserted


async def _insert_edges(session: AsyncSession, rows: list[Any]) -> int:
    if not rows:
        return 0
    inserted = 0
    for batch in _batched(rows, _INSERT_BATCH_SIZE):
        result = await session.execute(
            pg_insert(GraphEdge).values([row.__dict__ for row in batch]).on_conflict_do_nothing()
        )
        inserted += _rowcount(result)
    return inserted


def _batched(rows: list[Any], size: int) -> list[list[Any]]:
    return [rows[index : index + size] for index in range(0, len(rows), size)]


def _rowcount(result: Any) -> int:
    return max(0, int(getattr(result, "rowcount", 0) or 0))


def _temp_json_path() -> Path:
    with tempfile.NamedTemporaryFile(
        prefix="cappy-doc-import-",
        suffix=".json",
        delete=False,
    ) as handle:
        return Path(handle.name)
