from __future__ import annotations

import uuid

from app.adapters.primary.http import repo_graph as repo_graph_router
from app.adapters.primary.http.deps import get_db_session
from app.infrastructure.orm_models import Document, Repository
from app.main import app
from httpx import AsyncClient


class _GraphDbSession:
    def __init__(self, repo: Repository, document: Document | None = None) -> None:
        self.repo = repo
        self.document = document
        self.committed = False

    async def get(self, model, row_id):  # type: ignore[no-untyped-def]
        if model is Repository and row_id == self.repo.id:
            return self.repo
        if self.document is not None and model is Document and row_id == self.document.id:
            return self.document
        return None

    async def commit(self) -> None:
        self.committed = True


def _graph_shape() -> dict:
    return {
        "slug": "demo",
        "repo_path": "/repos/demo",
        "generated_at": "2026-05-23T00:00:00Z",
        "stats": {
            "files": 1,
            "code_files": 1,
            "modules": 1,
            "links": 0,
            "isolated": 0,
            "symbols": 1,
            "entrypoints": 1,
            "unreferenced_files": 0,
            "ui_actions": 0,
            "flows": 0,
        },
        "nodes": [
            {
                "id": "repo:demo",
                "label": "demo",
                "type": "repo",
                "path": "/repos/demo",
                "file_count": 0,
                "import_count": 0,
                "imported_by_count": 0,
                "isolated": False,
            }
        ],
        "edges": [],
        "files": [
            {
                "id": "file:src/app.js",
                "path": "src/app.js",
                "label": "app.js",
                "module": "src",
                "extension": "js",
                "line_count": 1,
                "symbol_count": 1,
                "imports": [],
                "imported_by": [],
                "import_count": 0,
                "imported_by_count": 0,
                "isolated": False,
                "entrypoint": True,
                "unreferenced": False,
                "symbols": ["symbol:src/app.js:1:start"],
            }
        ],
        "symbols": [
            {
                "id": "symbol:src/app.js:1:start",
                "name": "start",
                "kind": "function",
                "file_path": "src/app.js",
                "line": 1,
                "signature": "function start()",
                "exported": True,
                "container": "",
                "element": "",
                "handler": "",
            }
        ],
        "file_edges": [],
        "semantic_nodes": [],
        "semantic_edges": [],
        "findings": [],
    }


def _repo() -> Repository:
    repo_id = uuid.uuid4()
    sandbox_id = uuid.uuid4()
    return Repository(
        id=repo_id,
        slug="demo",
        name="Demo",
        clone_url="https://github.com/acme/demo.git",
        default_branch="main",
        confluence_url="",
        confluence_space="",
        confluence_labels=[],
        sandbox_id=sandbox_id,
        sandbox_status="cloned",
        sandbox_path="/repos/demo",
    )


def _document(repo_id: uuid.UUID) -> Document:
    return Document(
        id=uuid.uuid4(),
        repository_id=repo_id,
        source_type="markdown",
        source_uri="DATABASE_SCHEMA_Edu_CBE_2.md",
        title="DATABASE_SCHEMA_Edu_CBE_2.md",
        status="indexed",
        chunks_count=1,
    )


class TestMaterializedRepositoryGraphApi:
    async def test_materialized_graph_returns_public_shape(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        repo = _repo()
        fake_session = _GraphDbSession(repo)
        expected = _graph_shape()

        async def load_graph(session, *, repo, commit_sha):  # type: ignore[no-untyped-def]
            assert commit_sha == "abcdef1"
            return expected

        async def enqueue_graph(*args, **kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("materialized graph should not enqueue when rows exist")

        app.dependency_overrides[get_db_session] = lambda: fake_session
        monkeypatch.setattr(repo_graph_router, "load_materialized_repo_graph", load_graph)
        monkeypatch.setattr(repo_graph_router, "enqueue_graph_materialization", enqueue_graph)
        try:
            response = await client.get(
                f"/api/repositories/{repo.id}/graph?materialized=true&commit_sha=abcdef1",
                headers=admin_headers,
            )
        finally:
            app.dependency_overrides.pop(get_db_session, None)

        assert response.status_code == 200
        assert response.json() == expected

    async def test_materialized_graph_enqueues_when_missing(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        repo = _repo()
        fake_session = _GraphDbSession(repo)
        job_id = uuid.uuid4()
        enqueued: dict[str, object] = {}

        async def load_graph(session, *, repo, commit_sha):  # type: ignore[no-untyped-def]
            return None

        async def enqueue_graph(session, *, repo, commit_sha, max_files, priority=4):  # type: ignore[no-untyped-def]
            enqueued.update(
                {
                    "repo_id": repo.id,
                    "commit_sha": commit_sha,
                    "max_files": max_files,
                    "priority": priority,
                }
            )
            return job_id

        app.dependency_overrides[get_db_session] = lambda: fake_session
        monkeypatch.setattr(repo_graph_router, "load_materialized_repo_graph", load_graph)
        monkeypatch.setattr(repo_graph_router, "enqueue_graph_materialization", enqueue_graph)
        try:
            response = await client.get(
                f"/api/repositories/{repo.id}/graph"
                "?materialized=true&commit_sha=abcdef1&max_files=500",
                headers=admin_headers,
            )
        finally:
            app.dependency_overrides.pop(get_db_session, None)

        assert response.status_code == 202
        assert response.json() == {
            "job_id": str(job_id),
            "status": "materializing",
            "commit_sha": "abcdef1",
        }
        assert enqueued == {
            "repo_id": repo.id,
            "commit_sha": "abcdef1",
            "max_files": 500,
            "priority": 4,
        }
        assert fake_session.committed is True

    async def test_graph_invalidate_deletes_one_extractor_slice(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        repo = _repo()
        fake_session = _GraphDbSession(repo)
        invalidated: dict[str, object] = {}

        async def invalidate(session, *, repo_id, commit_sha, source_extractor):  # type: ignore[no-untyped-def]
            invalidated.update(
                {
                    "repo_id": repo_id,
                    "commit_sha": commit_sha,
                    "source_extractor": source_extractor,
                }
            )
            return {"nodes_deleted": 3, "edges_deleted": 4}

        app.dependency_overrides[get_db_session] = lambda: fake_session
        monkeypatch.setattr(repo_graph_router, "invalidate_extractor", invalidate)
        try:
            response = await client.post(
                f"/api/repositories/{repo.id}/graph/invalidate",
                headers=admin_headers,
                json={"commit_sha": "abcdef1", "source_extractor": "static_sql"},
            )
        finally:
            app.dependency_overrides.pop(get_db_session, None)

        assert response.status_code == 200
        assert response.json() == {
            "repo_id": str(repo.id),
            "commit_sha": "abcdef1",
            "source_extractor": "static_sql",
            "nodes_deleted": 3,
            "edges_deleted": 4,
        }
        assert invalidated == {
            "repo_id": repo.id,
            "commit_sha": "abcdef1",
            "source_extractor": "static_sql",
        }
        assert fake_session.committed is True

    async def test_document_graph_reimport_enqueues_doc_import(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        repo = _repo()
        document = _document(repo.id)
        fake_session = _GraphDbSession(repo, document)
        job_id = uuid.uuid4()
        captured: dict[str, object] = {}

        async def enqueue(session, *, repo, document, commit_sha=None, priority=4):  # type: ignore[no-untyped-def]
            captured.update(
                {
                    "repo_id": repo.id,
                    "document_id": document.id,
                    "commit_sha": commit_sha,
                    "priority": priority,
                }
            )
            return job_id

        from app.adapters.primary.http import documents as documents_router

        app.dependency_overrides[get_db_session] = lambda: fake_session
        monkeypatch.setattr(documents_router, "enqueue_doc_import_for_document", enqueue)
        try:
            response = await client.post(
                f"/api/repositories/{repo.id}/documents/{document.id}/reimport-graph",
                headers=admin_headers,
            )
        finally:
            app.dependency_overrides.pop(get_db_session, None)

        assert response.status_code == 202
        assert response.json() == {"job_id": str(job_id), "status": "materializing"}
        assert captured == {
            "repo_id": repo.id,
            "document_id": document.id,
            "commit_sha": None,
            "priority": 4,
        }
        assert fake_session.committed is True
