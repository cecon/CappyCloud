from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.adapters.primary.http import documents as documents_router
from app.adapters.primary.http.deps import get_db_session
from app.infrastructure.orm_models import Document, Repository
from app.main import app
from httpx import AsyncClient


class TestRepositoryDocumentsApi:
    async def test_upload_markdown_document_indexes_chunks(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        user_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        repo = _repo()
        fake_session = _DocumentsDbSession(repo)

        async def fake_ingest(session, document, **kwargs):  # type: ignore[no-untyped-def]
            document.status = "indexed"
            document.chunks_count = 1
            document.checksum = "checksum"
            document.indexed_at = datetime.now(UTC)

        app.dependency_overrides[get_db_session] = lambda: fake_session
        monkeypatch.setattr(documents_router, "ingest_document", fake_ingest)

        markdown = b"""# Banco de Dados `Edu_CBE_2`

## 5. Relacionamentos principais

#### dbo.tgFisVendItemImpo  (120 linhas)
- PK: EstaCod, VeDoCod, VeItSeq, TiImCod
- Colunas:
  - `ProdCod` int FK->dbo.tgProProd.ProdCod
  - `TiImCod` tinyint FK->dbo.tgFisTipoImpo.TiImCod
"""

        try:
            response = await client.post(
                f"/api/repositories/{repo.id}/documents/upload",
                data={"title": "Schema Edu_CBE_2"},
                files={
                    "file": (
                        "DATABASE_SCHEMA_Edu_CBE_2.md",
                        markdown,
                        "text/markdown",
                    )
                },
                headers=admin_headers,
            )

            assert response.status_code == 201
            body = response.json()
            assert body["source_type"] == "markdown"
            assert body["title"] == "Schema Edu_CBE_2"
            assert body["status"] == "indexed"
            assert body["chunks_count"] == 1

            listed = await client.get(
                f"/api/repositories/{repo.id}/documents",
                headers=admin_headers,
            )
            assert listed.status_code == 200
            assert listed.json()[0]["id"] == body["id"]

            denied = await client.get(
                f"/api/repositories/{repo.id}/documents",
                headers=user_headers,
            )
            assert denied.status_code == 404
        finally:
            app.dependency_overrides.pop(get_db_session, None)


class _DocumentsDbSession:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo
        self.documents: dict[uuid.UUID, Document] = {}

    async def get(self, model, row_id):  # type: ignore[no-untyped-def]
        if model is Repository and row_id == self.repo.id:
            return self.repo
        if model is Document:
            return self.documents.get(row_id)
        return None

    async def scalar(self, stmt):  # type: ignore[no-untyped-def]
        return None

    async def execute(self, stmt):  # type: ignore[no-untyped-def]
        return _DocumentsResult(list(self.documents.values()))

    def add(self, document: Document) -> None:
        now = datetime.now(UTC)
        document.version = document.version or 1
        document.created_at = document.created_at or now
        document.updated_at = document.updated_at or now
        self.documents[document.id] = document

    async def commit(self) -> None:
        pass

    async def flush(self) -> None:
        pass

    async def refresh(self, document: Document) -> None:
        pass


class _DocumentsResult:
    def __init__(self, documents: list[Document]) -> None:
        self._documents = documents

    def scalars(self) -> _DocumentsResult:
        return self

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.all())

    def all(self) -> list[Document]:
        return sorted(self._documents, key=lambda item: item.created_at, reverse=True)


def _repo() -> Repository:
    return Repository(
        id=uuid.uuid4(),
        slug="docs",
        name="Docs",
        clone_url="https://github.com/acme/docs.git",
        default_branch="main",
        confluence_url="",
        confluence_space="",
        confluence_labels=[],
        sandbox_id=uuid.uuid4(),
        sandbox_status="cloned",
        sandbox_path="/repos/docs",
    )
