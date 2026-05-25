from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from app.application.use_cases import repository_graph_reconciliation as use_case
from app.application.use_cases.repository_graph_reconciliation import (
    enqueue_graph_reconciliation,
    fetch_reconciliation_graph,
    find_resolution_edge,
    latest_reconciliation_summary,
    reconcile_repo_graph,
)
from app.infrastructure.orm_models import (
    GraphEdge,
    GraphReconciliationRun,
    Repository,
    SandboxSyncQueue,
)


def _repo() -> Repository:
    return Repository(
        id=uuid.uuid4(),
        slug="seller",
        name="Seller",
        clone_url="https://example.test/seller.git",
        default_branch="Master",
        sandbox_id=uuid.uuid4(),
        sandbox_status="cloned",
        sandbox_path="/repos/seller",
    )


@pytest.mark.asyncio
async def test_enqueue_graph_reconciliation_adds_queue_item() -> None:
    repo = _repo()
    session = _Session()

    job_id = await enqueue_graph_reconciliation(  # type: ignore[arg-type]
        session,
        repo=repo,
        commit_sha="abcdef1",
        mode="no-llm",
        llm_model="gpt-5.4-mini",
    )

    assert job_id
    item = session.added[0]
    assert isinstance(item, SandboxSyncQueue)
    assert item.operation == "reconcile_repo_graph"
    assert item.payload["mode"] == "no-llm"
    assert item.payload["llm_model"] == "gpt-5.4-mini"


@pytest.mark.asyncio
async def test_enqueue_graph_reconciliation_validates_sandbox_and_mode() -> None:
    repo = _repo()
    repo.sandbox_id = None

    with pytest.raises(ValueError, match="sem sandbox"):
        await enqueue_graph_reconciliation(  # type: ignore[arg-type]
            _Session(),
            repo=repo,
            commit_sha="abcdef1",
        )

    repo = _repo()
    with pytest.raises(ValueError, match="mode inválido"):
        await enqueue_graph_reconciliation(  # type: ignore[arg-type]
            _Session(),
            repo=repo,
            commit_sha="abcdef1",
            mode="batch",
        )


@pytest.mark.asyncio
async def test_reconcile_repo_graph_inserts_edges_and_records_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _repo()
    source_id = f"repo:{repo.id}@abcdef1:file:EmpresaBO.cs#M"
    target_id = f"repo:{repo.id}@abcdef1:doc:doc#table:dbo.Empresa"
    session = _Session(rowcount=1)

    async def fake_fetch(**kwargs):  # type: ignore[no-untyped-def]
        return {
            "nodes": [],
            "edges": [
                {
                    "id": "llm_gap:1",
                    "source": source_id,
                    "target": target_id,
                    "type": "resolves_to",
                    "source_extractor": "llm_gap",
                    "extractor_version": "0.2.0",
                    "evidence": {"file": "EmpresaBO.cs", "line_start": 1, "snippet": "Empresa"},
                    "attrs": {"original_edge_key": "key", "resolution_mode": "strict"},
                }
            ],
            "diagnostics": [{"code": "llm_no_match"}],
            "summary": {"refs_total": 1, "resolved_strict": 1},
            "extractor_version": "0.2.0",
            "llm_model": None,
            "mode": "no-llm",
        }

    monkeypatch.setattr(use_case, "fetch_reconciliation_graph", fake_fetch)

    result = await reconcile_repo_graph(  # type: ignore[arg-type]
        session,
        repo=repo,
        commit_sha="abcdef1",
        mode="no-llm",
    )

    assert result["edges_inserted"] == 1
    run = next(item for item in session.added if isinstance(item, GraphReconciliationRun))
    assert run.summary["refs_total"] == 1
    assert run.unresolved == [{"code": "llm_no_match"}]


@pytest.mark.asyncio
async def test_fetch_reconciliation_graph_invokes_cli_and_reads_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out_path = tmp_path / "reconciliation.json"
    captured: dict[str, Any] = {}

    class Proc:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            out_path.write_text('{"nodes":[],"edges":[],"summary":{"refs_total":0}}')
            return (b"ok", b"")

    async def fake_subprocess(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["args"] = args
        return Proc()

    monkeypatch.setattr(use_case, "_temp_json_path", lambda: out_path)
    monkeypatch.setattr(use_case.asyncio, "create_subprocess_exec", fake_subprocess)

    payload = await fetch_reconciliation_graph(
        repo_id=uuid.uuid4(),
        commit_sha="abcdef1",
        mode="no-llm",
        llm_model="gpt-5.4-mini",
        limit=10,
        db_url="postgresql://db/app",
    )

    assert payload["summary"]["refs_total"] == 0
    assert "--llm-model" in captured["args"]
    assert "--limit" in captured["args"]
    assert not out_path.exists()


@pytest.mark.asyncio
async def test_fetch_reconciliation_graph_raises_on_cli_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out_path = tmp_path / "reconciliation.json"

    class Proc:
        returncode = 1

        async def communicate(self) -> tuple[bytes, bytes]:
            return (b"", b"bad")

    async def fake_subprocess(*args, **kwargs):  # type: ignore[no-untyped-def]
        return Proc()

    monkeypatch.setattr(use_case, "_temp_json_path", lambda: out_path)
    monkeypatch.setattr(use_case.asyncio, "create_subprocess_exec", fake_subprocess)

    with pytest.raises(RuntimeError, match="llm_reconciliation failed"):
        await fetch_reconciliation_graph(
            repo_id=uuid.uuid4(),
            commit_sha="abcdef1",
            db_url="postgresql://db/app",
        )


@pytest.mark.asyncio
async def test_latest_reconciliation_summary_paginates_unresolved() -> None:
    repo = _repo()
    run = GraphReconciliationRun(
        id=uuid.uuid4(),
        repo_id=repo.id,
        commit_sha="abcdef1",
        extractor_version="0.2.0",
        mode="all",
        summary={"refs_total": 3},
        unresolved=[{"ref_name": "A"}, {"ref_name": "B"}, {"ref_name": "C"}],
        created_at=datetime(2026, 5, 23, tzinfo=UTC),
    )

    summary = await latest_reconciliation_summary(  # type: ignore[arg-type]
        _Session(scalar=run),
        repo_id=repo.id,
        commit_sha="abcdef1",
        limit=1,
        offset=1,
    )

    assert summary is not None
    assert summary["unresolved_total"] == 3
    assert summary["unresolved"] == [{"ref_name": "B"}]


@pytest.mark.asyncio
async def test_latest_reconciliation_summary_returns_none_without_run() -> None:
    assert (
        await latest_reconciliation_summary(  # type: ignore[arg-type]
            _Session(scalar=None),
            repo_id=uuid.uuid4(),
            commit_sha="abcdef1",
        )
        is None
    )


@pytest.mark.asyncio
async def test_find_resolution_edge_by_original_edge_id() -> None:
    repo = _repo()
    original = GraphEdge(
        id=10,
        repo_id=repo.id,
        commit_sha="abcdef1",
        source_id="method",
        target_external="ref:Empresa",
        type="references",
        evidence={},
        confidence="low",
        source_extractor="static_roslyn",
        extractor_version="0.2.0",
    )
    resolved = GraphEdge(
        id=11,
        repo_id=repo.id,
        commit_sha="abcdef1",
        source_id="method",
        target_id="table",
        type="resolves_to",
        evidence={"attrs": {"original_edge_key": "computed"}},
        confidence="high",
        source_extractor="llm_gap",
        extractor_version="0.2.0",
    )

    edge = await find_resolution_edge(  # type: ignore[arg-type]
        _Session(get_item=original, scalar=resolved),
        repo_id=repo.id,
        commit_sha="abcdef1",
        edge_id=10,
    )

    assert edge is not None
    assert edge["id"] == 11
    assert edge["target_id"] == "table"


@pytest.mark.asyncio
async def test_find_resolution_edge_returns_none_without_key_or_original() -> None:
    assert (
        await find_resolution_edge(  # type: ignore[arg-type]
            _Session(),
            repo_id=uuid.uuid4(),
            commit_sha="abcdef1",
        )
        is None
    )
    assert (
        await find_resolution_edge(  # type: ignore[arg-type]
            _Session(get_item=None),
            repo_id=uuid.uuid4(),
            commit_sha="abcdef1",
            edge_id=99,
        )
        is None
    )


@pytest.mark.asyncio
async def test_insert_edges_noops_empty_rows() -> None:
    assert await use_case._insert_edges(_Session(), []) == 0


def test_temp_json_path_creates_unique_path() -> None:
    path = use_case._temp_json_path()
    try:
        assert path.name.startswith("cappy-llm-reconciliation-")
        assert path.suffix == ".json"
        assert path.exists()
    finally:
        path.unlink(missing_ok=True)


class _Result:
    def __init__(self, rowcount: int, scalar: Any = None) -> None:
        self.rowcount = rowcount
        self._scalar = scalar

    def scalar_one_or_none(self) -> Any:
        return self._scalar


class _Session:
    def __init__(self, rowcount: int = 0, scalar: Any = None, get_item: Any = None) -> None:
        self.rowcount = rowcount
        self.scalar = scalar
        self.get_item = get_item
        self.added: list[object] = []

    def add(self, item: object) -> None:
        self.added.append(item)

    async def execute(self, stmt: Any) -> _Result:
        return _Result(self.rowcount, self.scalar)

    async def get(self, model: Any, item_id: Any) -> Any:
        return self.get_item
