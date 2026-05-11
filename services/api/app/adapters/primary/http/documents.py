"""Documents HTTP router — CRUD de documentos de referência por repositório.

Endpoints:
  POST   /repositories/{repo_id}/documents           cria por URL/texto (JSON)
  POST   /repositories/{repo_id}/documents/upload    cria por upload (PDF/XLSX)
  GET    /repositories/{repo_id}/documents           lista documentos do repo
  GET    /documents/{doc_id}                         detalhe
  POST   /documents/{doc_id}/reindex                 bumpa version + re-extrai
  DELETE /documents/{doc_id}                         apaga doc + chunks (cascade)
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import get_authenticated_user, get_db_session
from app.domain.entities import User
from app.infrastructure.document_ingester import IngesterError, ingest_document
from app.infrastructure.orm_models import Document, Repository
from app.schemas import DocumentCreate, DocumentOut

router = APIRouter(tags=["documents"])
log = logging.getLogger(__name__)

_UPLOAD_MAX_BYTES = 25 * 1024 * 1024  # 25 MB


async def _get_repo_or_404(session: AsyncSession, repo_id: uuid.UUID) -> Repository:
    repo = await session.get(Repository, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repositório não encontrado")
    return repo


async def _get_doc_or_404(session: AsyncSession, doc_id: uuid.UUID) -> Document:
    doc = await session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    return doc


@router.get("/repositories/{repo_id}/documents", response_model=list[DocumentOut])
async def list_documents(
    repo_id: uuid.UUID,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[DocumentOut]:
    await _get_repo_or_404(session, repo_id)
    rows = await session.execute(
        select(Document)
        .where(Document.repository_id == repo_id)
        .order_by(Document.created_at.desc())
    )
    return [DocumentOut.model_validate(d) for d in rows.scalars()]


@router.post("/repositories/{repo_id}/documents", response_model=DocumentOut, status_code=201)
async def create_document(
    repo_id: uuid.UUID,
    body: DocumentCreate,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DocumentOut:
    """Cria um documento por URL ou texto colado e ingere de imediato."""
    await _get_repo_or_404(session, repo_id)
    source_type = body.normalized_source_type()
    if source_type in {"pdf", "xlsx"}:
        raise HTTPException(
            status_code=400,
            detail=f"Para {source_type}, use o endpoint /upload (multipart).",
        )

    title = (body.title or body.source_uri or "Documento")[:512]
    doc = Document(
        id=uuid.uuid4(),
        repository_id=repo_id,
        source_type=source_type,
        source_uri=body.source_uri or "",
        title=title,
    )
    session.add(doc)
    await session.flush()

    try:
        await ingest_document(session, doc, text_content=body.content)
    except IngesterError as exc:
        await session.commit()  # persiste status='error' + error_message
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await session.commit()
    await session.refresh(doc)
    return DocumentOut.model_validate(doc)


@router.post(
    "/repositories/{repo_id}/documents/upload",
    response_model=DocumentOut,
    status_code=201,
)
async def upload_document(
    repo_id: uuid.UUID,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    file: Annotated[UploadFile, File(description="PDF ou XLSX (máx 25 MB).")],
    title: Annotated[str | None, Form()] = None,
) -> DocumentOut:
    await _get_repo_or_404(session, repo_id)

    name = (file.filename or "").lower()
    if name.endswith(".pdf"):
        source_type = "pdf"
    elif name.endswith((".xlsx", ".xlsm")):
        source_type = "xlsx"
    else:
        raise HTTPException(
            status_code=400, detail="Extensão não suportada. Use .pdf, .xlsx ou .xlsm."
        )

    blob = await file.read()
    if len(blob) > _UPLOAD_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Ficheiro acima do limite (25 MB).")
    if not blob:
        raise HTTPException(status_code=400, detail="Ficheiro vazio.")

    doc = Document(
        id=uuid.uuid4(),
        repository_id=repo_id,
        source_type=source_type,
        source_uri=file.filename or "",
        title=(title or file.filename or "Documento")[:512],
    )
    session.add(doc)
    await session.flush()

    try:
        await ingest_document(session, doc, raw_blob=blob)
    except IngesterError as exc:
        await session.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await session.commit()
    await session.refresh(doc)
    return DocumentOut.model_validate(doc)


@router.get("/documents/{doc_id}", response_model=DocumentOut)
async def get_document(
    doc_id: uuid.UUID,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DocumentOut:
    doc = await _get_doc_or_404(session, doc_id)
    return DocumentOut.model_validate(doc)


@router.post("/documents/{doc_id}/reindex", response_model=DocumentOut)
async def reindex_document(
    doc_id: uuid.UUID,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DocumentOut:
    """Re-extrai (apenas para fontes URL/texto). Para PDF/XLSX, faça novo upload.

    Bumpa ``version`` e dispara nova extracção. Os chunks antigos são
    removidos automaticamente (cascade do FK skills.document_id).
    """
    doc = await _get_doc_or_404(session, doc_id)
    if doc.source_type in {"pdf", "xlsx"}:
        raise HTTPException(
            status_code=400,
            detail="Reindex de PDF/XLSX exige novo upload (binário não é guardado).",
        )

    doc.version += 1
    try:
        await ingest_document(session, doc)
    except IngesterError as exc:
        await session.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await session.commit()
    await session.refresh(doc)
    return DocumentOut.model_validate(doc)


@router.delete("/documents/{doc_id}", status_code=204)
async def delete_document(
    doc_id: uuid.UUID,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    doc = await _get_doc_or_404(session, doc_id)
    await session.delete(doc)
    await session.commit()
