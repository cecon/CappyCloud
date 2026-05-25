from __future__ import annotations

import uuid
from typing import Any

import pytest
from app.application.use_cases import repository_graph_materialization as materialization
from app.application.use_cases.repository_graph_materialization import (
    enqueue_graph_materialization,
    invalidate_extractor,
    latest_materialized_commit_sha,
    load_materialized_repo_graph,
    materialize_repo_graph,
)
from app.infrastructure.orm_models import GraphNode, Repository, Sandbox, SandboxSyncQueue


def _repo() -> Repository:
    return Repository(
        id=uuid.uuid4(),
        slug="demo",
        name="Demo",
        clone_url="https://example.test/demo.git",
        default_branch="main",
        sandbox_id=uuid.uuid4(),
        sandbox_status="cloned",
        sandbox_path="/repos/demo",
    )


def _sandbox(repo: Repository) -> Sandbox:
    return Sandbox(
        id=repo.sandbox_id,
        name="default",
        runtime="compose",
        host="sandbox",
        session_port=8080,
    )


@pytest.mark.asyncio
async def test_materialize_repo_graph_merges_doc_import_and_batches_inserts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _repo()
    document_id = uuid.uuid4()
    session = _Session(sandbox=_sandbox(repo), rowcounts=[2, 1])
    provider = _Provider(_sandbox_graph())
    doc_id = f"repo:{repo.id}@abcdef1:doc:{document_id}#document:{document_id}"
    table_id = f"repo:{repo.id}@abcdef1:doc:{document_id}#table:dbo.users"

    async def list_documents(session, repo_id):  # type: ignore[no-untyped-def]
        return [document_id]

    async def fetch_doc_graph(**kwargs):  # type: ignore[no-untyped-def]
        return {
            "nodes": [
                {
                    "id": doc_id,
                    "type": "document",
                    "name": "schema.md",
                    "source_extractor": "doc_import",
                    "extractor_version": "0.1.0",
                    "attrs": {"document_id": str(document_id)},
                },
                {
                    "id": table_id,
                    "type": "table",
                    "name": "dbo.users",
                    "source_extractor": "doc_import",
                    "extractor_version": "0.1.0",
                    "attrs": {"document_id": str(document_id), "chunk_index": 1},
                },
            ],
            "edges": [{"source": doc_id, "target": table_id, "type": "defines"}],
            "diagnostics": [],
        }

    monkeypatch.setattr(materialization, "list_doc_import_document_ids", list_documents)
    monkeypatch.setattr(materialization, "fetch_doc_import_graph", fetch_doc_graph)

    result = await materialize_repo_graph(  # type: ignore[arg-type]
        session,
        repo=repo,
        commit_sha="abcdef1",
        max_files=500,
        provider=provider,
    )

    assert result.nodes_inserted == 2
    assert result.edges_inserted == 1
    assert provider.calls == [{"slug": "demo", "max_files": 500}]
    assert session.execute_calls == 2


@pytest.mark.asyncio
async def test_materialize_repo_graph_requires_repo_sandbox() -> None:
    repo = _repo()
    repo.sandbox_id = None

    with pytest.raises(ValueError, match="sem sandbox"):
        await materialize_repo_graph(  # type: ignore[arg-type]
            _Session(),
            repo=repo,
            commit_sha="abcdef1",
        )


@pytest.mark.asyncio
async def test_materialize_repo_graph_requires_existing_sandbox() -> None:
    repo = _repo()

    with pytest.raises(ValueError, match="Sandbox do repositório"):
        await materialize_repo_graph(  # type: ignore[arg-type]
            _Session(),
            repo=repo,
            commit_sha="abcdef1",
        )


@pytest.mark.asyncio
async def test_load_materialized_repo_graph_returns_none_without_rows() -> None:
    repo = _repo()
    session = _Session(node_rows=[])

    graph = await load_materialized_repo_graph(  # type: ignore[arg-type]
        session,
        repo=repo,
        commit_sha="abcdef1",
    )

    assert graph is None


@pytest.mark.asyncio
async def test_latest_materialized_commit_sha_reads_first_row() -> None:
    commit = await latest_materialized_commit_sha(  # type: ignore[arg-type]
        _Session(first=("abcdef1",)),
        uuid.uuid4(),
    )

    assert commit == "abcdef1"


@pytest.mark.asyncio
async def test_enqueue_graph_materialization_adds_queue_item() -> None:
    repo = _repo()
    session = _Session()

    job_id = await enqueue_graph_materialization(  # type: ignore[arg-type]
        session,
        repo=repo,
        commit_sha="abcdef1",
        max_files=500,
    )

    assert job_id
    assert len(session.added) == 1
    item = session.added[0]
    assert isinstance(item, SandboxSyncQueue)
    assert item.operation == "materialize_repo_graph"
    assert item.payload["commit_sha"] == "abcdef1"


@pytest.mark.asyncio
async def test_enqueue_graph_materialization_requires_sandbox() -> None:
    repo = _repo()
    repo.sandbox_id = None

    with pytest.raises(ValueError, match="sem sandbox"):
        await enqueue_graph_materialization(  # type: ignore[arg-type]
            _Session(),
            repo=repo,
            commit_sha="abcdef1",
        )


@pytest.mark.asyncio
async def test_invalidate_extractor_returns_deleted_counts() -> None:
    result = await invalidate_extractor(  # type: ignore[arg-type]
        _Session(rowcounts=[4, 3]),
        repo_id=uuid.uuid4(),
        commit_sha="abcdef1",
        source_extractor="doc_import",
    )

    assert result == {"edges_deleted": 4, "nodes_deleted": 3}


class _Provider:
    def __init__(self, graph: dict[str, Any]) -> None:
        self.graph = graph
        self.calls: list[dict[str, Any]] = []

    async def fetch_graph(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append({"slug": kwargs["slug"], "max_files": kwargs["max_files"]})
        return self.graph


class _Result:
    def __init__(
        self,
        *,
        rowcount: int = 0,
        node_rows: list[GraphNode] | None = None,
        first: tuple[str] | None = None,
    ) -> None:
        self.rowcount = rowcount
        self._node_rows = node_rows or []
        self._first = first

    def scalars(self) -> _Result:
        return self

    def all(self) -> list[GraphNode]:
        return self._node_rows

    def first(self) -> tuple[str] | None:
        return self._first


class _Session:
    def __init__(
        self,
        *,
        sandbox: Sandbox | None = None,
        rowcounts: list[int] | None = None,
        node_rows: list[GraphNode] | None = None,
        first: tuple[str] | None = None,
    ) -> None:
        self.sandbox = sandbox
        self.rowcounts = rowcounts or []
        self.node_rows = node_rows
        self.first = first
        self.added: list[object] = []
        self.execute_calls = 0

    async def get(self, model, row_id):  # type: ignore[no-untyped-def]
        if model is Sandbox and self.sandbox is not None and row_id == self.sandbox.id:
            return self.sandbox
        return None

    async def execute(self, stmt):  # type: ignore[no-untyped-def]
        self.execute_calls += 1
        if self.node_rows is not None:
            return _Result(node_rows=self.node_rows)
        if self.first is not None:
            return _Result(first=self.first)
        rowcount = self.rowcounts.pop(0) if self.rowcounts else 0
        return _Result(rowcount=rowcount)

    def add(self, item: object) -> None:
        self.added.append(item)


def _sandbox_graph() -> dict[str, Any]:
    return {
        "slug": "demo",
        "repo_path": "/repos/demo",
        "generated_at": "",
        "stats": {},
        "nodes": [
            {
                "id": "repo:demo",
                "type": "repo",
                "label": "demo",
                "name": "demo",
                "path": "/repos/demo",
            }
        ],
        "edges": [],
        "files": [],
        "symbols": [],
        "file_edges": [],
        "semantic_nodes": [],
        "semantic_edges": [],
        "findings": [],
    }
