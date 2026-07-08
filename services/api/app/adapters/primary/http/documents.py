"""Reference document HTTP router for repositories."""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import get_authenticated_user, get_db_session
from app.domain.entities import User, UserRole
from app.infrastructure.document_ingester import IngesterError, ingest_document
from app.infrastructure.orm_models import Document, Repository
from app.infrastructure.orm_models_access import UserRepositoryAccess
from app.schemas import DocumentCreate, DocumentOut

router = APIRouter(tags=["documents"])
log = logging.getLogger(__name__)

_UPLOAD_MAX_BYTES = 25 * 1024 * 1024
_REUPLOAD_ONLY_TYPES = {"pdf", "xlsx", "markdown", "txt", "docx"}


def _source_type_from_filename(filename: str) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        return "pdf"
    if name.endswith((".xlsx", ".xlsm")):
        return "xlsx"
    if name.endswith((".md", ".markdown")):
        return "markdown"
    if name.endswith(".txt"):
        return "txt"
    if name.endswith(".docx"):
        return "docx"
    raise HTTPException(
        status_code=400,
        detail="Extensao nao suportada. Use .pdf, .xlsx, .xlsm, .md, .markdown, .txt ou .docx.",
    )


async def _get_repo_or_404(
    session: AsyncSession,
    current: User,
    repo_id: uuid.UUID,
) -> Repository:
    repo = await session.get(Repository, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repositorio nao encontrado")
    if current.role is not UserRole.ADMIN:
        allowed = await session.scalar(
            select(UserRepositoryAccess.id)
            .where(UserRepositoryAccess.user_id == current.id)
            .where(UserRepositoryAccess.repository_id == repo.id)
            .limit(1)
        )
        if allowed is None:
            raise HTTPException(status_code=404, detail="Repositorio nao encontrado")
    return repo


async def _get_doc_or_404(
    session: AsyncSession,
    current: User,
    doc_id: uuid.UUID,
) -> Document:
    doc = await session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Documento nao encontrado")
    await _get_repo_or_404(session, current, doc.repository_id)
    return doc


@router.get("/repositories/{repo_id}/documents", response_model=list[DocumentOut])
async def list_documents(
    repo_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[DocumentOut]:
    await _get_repo_or_404(session, current, repo_id)
    rows = await session.execute(
        select(Document)
        .where(Document.repository_id == repo_id)
        .order_by(Document.created_at.desc())
    )
    return [DocumentOut.model_validate(document) for document in rows.scalars()]


@router.post("/repositories/{repo_id}/documents", response_model=DocumentOut, status_code=201)
async def create_document(
    repo_id: uuid.UUID,
    body: DocumentCreate,
    current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DocumentOut:
    await _get_repo_or_404(session, current, repo_id)
    source_type = body.normalized_source_type()
    if source_type in {"pdf", "xlsx"}:
        raise HTTPException(
            status_code=400,
            detail=f"Para {source_type}, use o endpoint /upload (multipart).",
        )

    document = Document(
        id=uuid.uuid4(),
        repository_id=repo_id,
        source_type=source_type,
        source_uri=body.source_uri or "",
        title=(body.title or body.source_uri or "Documento")[:512],
    )
    session.add(document)
    await session.flush()

    try:
        await ingest_document(session, document, text_content=body.content)
    except IngesterError as exc:
        await session.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await session.commit()
    await session.refresh(document)
    return DocumentOut.model_validate(document)


@router.post(
    "/repositories/{repo_id}/documents/upload",
    response_model=DocumentOut,
    status_code=201,
)
async def upload_document(
    repo_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    file: Annotated[
        UploadFile,
        File(description="PDF, XLSX, Markdown, TXT ou DOCX (max 25 MB)."),
    ],
    title: Annotated[str | None, Form()] = None,
) -> DocumentOut:
    await _get_repo_or_404(session, current, repo_id)
    source_type = _source_type_from_filename(file.filename or "")

    blob = await file.read()
    if len(blob) > _UPLOAD_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Ficheiro acima do limite (25 MB).")
    if not blob:
        raise HTTPException(status_code=400, detail="Ficheiro vazio.")

    document = Document(
        id=uuid.uuid4(),
        repository_id=repo_id,
        source_type=source_type,
        source_uri=file.filename or "",
        title=(title or file.filename or "Documento")[:512],
    )
    session.add(document)
    await session.flush()

    try:
        await ingest_document(session, document, raw_blob=blob)
    except IngesterError as exc:
        await session.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await session.commit()
    await session.refresh(document)
    return DocumentOut.model_validate(document)


@router.get("/documents/{doc_id}", response_model=DocumentOut)
async def get_document(
    doc_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DocumentOut:
    document = await _get_doc_or_404(session, current, doc_id)
    return DocumentOut.model_validate(document)


@router.post("/documents/{doc_id}/reindex", response_model=DocumentOut)
async def reindex_document(
    doc_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DocumentOut:
    document = await _get_doc_or_404(session, current, doc_id)
    if document.source_type in _REUPLOAD_ONLY_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Reindex deste tipo de arquivo exige novo upload.",
        )

    document.version += 1
    try:
        await ingest_document(session, document)
    except IngesterError as exc:
        await session.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await session.commit()
    await session.refresh(document)
    return DocumentOut.model_validate(document)


@router.delete("/documents/{doc_id}", status_code=204)
async def delete_document(
    doc_id: uuid.UUID,
    current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    document = await _get_doc_or_404(session, current, doc_id)
    await session.delete(document)
    await session.commit()
