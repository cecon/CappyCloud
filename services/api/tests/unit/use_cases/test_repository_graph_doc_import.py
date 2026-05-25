from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pytest
from app.application.use_cases import repository_graph_doc_import as use_case
from app.application.use_cases.repository_graph_doc_import import (
    append_doc_import_graph,
    enqueue_doc_import_for_document,
    fetch_doc_import_graph,
    list_doc_import_document_ids,
    materialize_doc_import,
    resolve_doc_import_commit_sha,
)
from app.infrastructure.orm_models import Document, Repository, Sandbox, SandboxSyncQueue


class _Session:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, item: object) -> None:
        self.added.append(item)


def _repo() -> Repository:
    return Repository(
        id=uuid.uuid4(),
        slug="Seller",
        name="Seller",
        clone_url="https://example.test/seller.git",
        default_branch="Master",
        sandbox_id=uuid.uuid4(),
        sandbox_status="cloned",
        sandbox_path="/repos/Seller",
    )


def _document(repo_id: uuid.UUID) -> Document:
    return Document(
        id=uuid.uuid4(),
        repository_id=repo_id,
        source_type="markdown",
        source_uri="DATABASE_SCHEMA_Edu_CBE_2.md",
        title="DATABASE_SCHEMA_Edu_CBE_2.md",
        status="indexed",
        chunks_count=246,
    )


@pytest.mark.asyncio
async def test_enqueue_doc_import_for_indexed_markdown_document() -> None:
    session = _Session()
    repo = _repo()
    document = _document(repo.id)

    job_id = await enqueue_doc_import_for_document(  # type: ignore[arg-type]
        session,
        repo=repo,
        document=document,
    )

    assert job_id is not None
    assert len(session.added) == 1
    item = session.added[0]
    assert isinstance(item, SandboxSyncQueue)
    assert item.operation == "doc_import_for_document"
    assert item.sandbox_id == repo.sandbox_id
    assert item.payload["repo_id"] == str(repo.id)
    assert item.payload["document_id"] == str(document.id)


@pytest.mark.asyncio
async def test_enqueue_doc_import_skips_unsupported_or_unindexed_document() -> None:
    session = _Session()
    repo = _repo()
    document = _document(repo.id)
    document.status = "processing"

    job_id = await enqueue_doc_import_for_document(  # type: ignore[arg-type]
        session,
        repo=repo,
        document=document,
    )

    assert job_id is None
    assert session.added == []


@pytest.mark.asyncio
async def test_enqueue_doc_import_skips_repo_without_sandbox() -> None:
    session = _Session()
    repo = _repo()
    repo.sandbox_id = None
    document = _document(repo.id)

    job_id = await enqueue_doc_import_for_document(  # type: ignore[arg-type]
        session,
        repo=repo,
        document=document,
    )

    assert job_id is None
    assert session.added == []


@pytest.mark.asyncio
async def test_list_doc_import_document_ids_returns_ordered_scalars() -> None:
    document_id = uuid.uuid4()
    session = _ListDocumentsSession([document_id])

    result = await list_doc_import_document_ids(  # type: ignore[arg-type]
        session,
        uuid.uuid4(),
        [document_id],
    )

    assert result == [document_id]


def test_append_doc_import_graph_merges_nodes_edges_and_findings() -> None:
    base = {"stats": {"symbols": 1, "flows": 2}}
    doc_graph = {
        "nodes": [{"id": "n1", "type": "document"}],
        "edges": [{"source": "n1", "target": "n2", "type": "defines"}],
        "diagnostics": [
            {
                "document_id": "doc-1",
                "level": "info",
                "code": "unmatched_line",
                "message": "ignored",
                "line": 10,
            }
        ],
    }

    append_doc_import_graph(base, doc_graph)

    assert base["semantic_nodes"] == doc_graph["nodes"]
    assert base["semantic_edges"] == doc_graph["edges"]
    assert base["stats"] == {"symbols": 2, "flows": 3}
    assert base["findings"][0]["source"] == "doc_import"


def test_append_doc_import_graph_noops_empty_payload() -> None:
    base: dict[str, Any] = {}

    append_doc_import_graph(base, {"nodes": [], "edges": [], "diagnostics": []})

    assert base == {}


@pytest.mark.asyncio
async def test_fetch_doc_import_graph_invokes_cli_and_reads_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out_path = tmp_path / "doc-import.json"
    captured: dict[str, Any] = {}

    class Proc:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            out_path.write_text(json.dumps({"nodes": [{"id": "n1"}], "edges": []}))
            return (b"done", b"")

    async def fake_subprocess(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["args"] = args
        return Proc()

    monkeypatch.setattr(use_case, "_temp_json_path", lambda: out_path)
    monkeypatch.setattr(use_case.asyncio, "create_subprocess_exec", fake_subprocess)

    payload = await fetch_doc_import_graph(
        repo_id=uuid.uuid4(),
        commit_sha="abcdef1",
        document_ids=[uuid.uuid4()],
        db_url="postgresql://user:pass@db/app",
    )

    assert payload == {"nodes": [{"id": "n1"}], "edges": []}
    assert "cappy-doc-import-extractor" in captured["args"]
    assert "--document-ids" in captured["args"]
    assert not out_path.exists()


@pytest.mark.asyncio
async def test_fetch_doc_import_graph_raises_on_cli_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out_path = tmp_path / "doc-import.json"

    class Proc:
        returncode = 1

        async def communicate(self) -> tuple[bytes, bytes]:
            return (b"", b"bad args")

    async def fake_subprocess(*args, **kwargs):  # type: ignore[no-untyped-def]
        return Proc()

    monkeypatch.setattr(use_case, "_temp_json_path", lambda: out_path)
    monkeypatch.setattr(use_case.asyncio, "create_subprocess_exec", fake_subprocess)

    with pytest.raises(RuntimeError, match="doc_import extractor failed"):
        await fetch_doc_import_graph(
            repo_id=uuid.uuid4(),
            commit_sha="abcdef1",
            db_url="postgresql://user:pass@db/app",
        )


@pytest.mark.asyncio
async def test_materialize_doc_import_translates_and_inserts_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _repo()
    document_id = uuid.uuid4()
    session = _InsertSession()

    async def list_documents(session, repo_id, document_ids=None):  # type: ignore[no-untyped-def]
        return [document_id]

    async def fetch_graph(**kwargs):  # type: ignore[no-untyped-def]
        return {
            "nodes": [
                {
                    "id": f"repo:{repo.id}@abcdef1:doc:{document_id}#document:{document_id}",
                    "type": "document",
                    "name": "schema.md",
                    "source_extractor": "doc_import",
                    "extractor_version": "0.1.0",
                    "attrs": {"document_id": str(document_id)},
                }
            ],
            "edges": [],
            "diagnostics": [],
        }

    monkeypatch.setattr(use_case, "list_doc_import_document_ids", list_documents)
    monkeypatch.setattr(use_case, "fetch_doc_import_graph", fetch_graph)

    result = await materialize_doc_import(session, repo=repo, commit_sha="abcdef1")  # type: ignore[arg-type]

    assert result == {"nodes_inserted": 1, "edges_inserted": 0}
    assert session.execute_calls == 1


@pytest.mark.asyncio
async def test_materialize_doc_import_returns_zero_without_documents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def list_documents(session, repo_id, document_ids=None):  # type: ignore[no-untyped-def]
        return []

    monkeypatch.setattr(use_case, "list_doc_import_document_ids", list_documents)

    result = await materialize_doc_import(  # type: ignore[arg-type]
        _InsertSession(),
        repo=_repo(),
        commit_sha="abcdef1",
    )

    assert result == {"nodes_inserted": 0, "edges_inserted": 0}


@pytest.mark.asyncio
async def test_resolve_doc_import_commit_sha_prefers_latest_materialized() -> None:
    repo = _repo()
    sandbox = Sandbox(
        id=repo.sandbox_id,
        name="default",
        runtime="compose",
        host="sandbox",
        session_port=8080,
    )
    session = _LatestCommitSession("abcdef1")

    commit = await resolve_doc_import_commit_sha(  # type: ignore[arg-type]
        session=session,
        repo=repo,
        sandbox=sandbox,
    )

    assert commit == "abcdef1"


@pytest.mark.asyncio
async def test_resolve_doc_import_commit_sha_uses_provider_when_no_materialized_commit() -> None:
    repo = _repo()
    sandbox = Sandbox(
        id=repo.sandbox_id,
        name="default",
        runtime="compose",
        host="sandbox",
        session_port=8080,
    )
    provider = _CommitProvider("fedcba9")

    commit = await resolve_doc_import_commit_sha(  # type: ignore[arg-type]
        session=_LatestCommitSession(None),
        repo=repo,
        sandbox=sandbox,
        provider=provider,  # type: ignore[arg-type]
    )

    assert commit == "fedcba9"
    assert provider.refs == ["Master"]


class _InsertResult:
    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount


class _InsertSession:
    def __init__(self) -> None:
        self.execute_calls = 0

    async def execute(self, stmt):  # type: ignore[no-untyped-def]
        self.execute_calls += 1
        return _InsertResult(1)


class _LatestCommitSession:
    def __init__(self, commit_sha: str | None) -> None:
        self.commit_sha = commit_sha

    async def execute(self, stmt):  # type: ignore[no-untyped-def]
        return _LatestCommitResult(self.commit_sha)


class _LatestCommitResult:
    def __init__(self, commit_sha: str | None) -> None:
        self.commit_sha = commit_sha

    def first(self) -> tuple[str] | None:
        if self.commit_sha is None:
            return None
        return (self.commit_sha,)


class _ScalarsResult:
    def __init__(self, values: list[uuid.UUID]) -> None:
        self.values = values

    def scalars(self) -> _ScalarsResult:
        return self

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.values)


class _ListDocumentsSession:
    def __init__(self, values: list[uuid.UUID]) -> None:
        self.values = values

    async def execute(self, stmt):  # type: ignore[no-untyped-def]
        return _ScalarsResult(self.values)


class _CommitProvider:
    def __init__(self, commit_sha: str) -> None:
        self.commit_sha = commit_sha
        self.refs: list[str] = []

    async def fetch_commit_sha(self, **kwargs):  # type: ignore[no-untyped-def]
        self.refs.append(kwargs["ref"])
        return self.commit_sha
