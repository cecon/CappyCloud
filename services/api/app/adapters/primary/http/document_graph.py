"""Internal search router for document-scoped schema graphs."""

from __future__ import annotations

import os
import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import get_authenticated_user, get_db_session
from app.domain.entities import User
from app.infrastructure.database import async_session_factory
from app.infrastructure.document_graph import graph_summary
from app.infrastructure.orm_models import Document
from app.infrastructure.orm_models_document_graph import DocumentGraphNode
from app.schemas_document_graph import DocumentGraphSearchResult

router = APIRouter(prefix="/document-graph", tags=["document-graph"])

_INTERNAL_TOKEN = os.getenv("INTERNAL_API_TOKEN", "").strip()
_WORD_RE = re.compile(r"[A-Za-z_][\w.]{2,}")


async def search_document_graph(
    session: AsyncSession,
    q: str,
    limit: int,
    repo_ids: list[uuid.UUID] | None = None,
) -> list[DocumentGraphSearchResult]:
    terms = _query_terms(q)
    if not terms:
        return []

    filters = [DocumentGraphNode.kind == "table"]
    if repo_ids:
        filters.append(DocumentGraphNode.repository_id.in_(repo_ids))
    predicates = []
    for term in terms:
        pattern = f"%{term}%"
        predicates.append(DocumentGraphNode.name.ilike(pattern))
        predicates.append(DocumentGraphNode.node_key.ilike(pattern))
    fetch_limit = min(max(limit * 20, 50), 200)
    rows = await session.execute(
        select(DocumentGraphNode, Document)
        .join(Document, Document.id == DocumentGraphNode.document_id)
        .where(*filters, or_(*predicates))
        .order_by(DocumentGraphNode.name)
        .limit(fetch_limit)
    )
    out: list[DocumentGraphSearchResult] = []
    for node, document in rows.all():
        out.append(
            DocumentGraphSearchResult(
                title=f"{document.title} :: {node.name}",
                source_url=document.source_uri or None,
                summary=graph_summary(node),
                score=_score_node(node, terms),
            )
        )
    return sorted(out, key=lambda item: item.score, reverse=True)[:limit]


@router.get("/_search/run", response_model=list[DocumentGraphSearchResult])
async def search_document_graph_run(
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    q: str = Query(min_length=1, max_length=512),
    limit: int = Query(default=5, ge=1, le=20),
    repo_id: Annotated[list[uuid.UUID] | None, Query()] = None,
) -> list[DocumentGraphSearchResult]:
    return await search_document_graph(session, q, limit, repo_id)


@router.get("/_search/internal", response_model=list[DocumentGraphSearchResult])
async def search_document_graph_internal(
    q: str = Query(min_length=1, max_length=512),
    limit: int = Query(default=5, ge=1, le=20),
    repo_id: Annotated[list[uuid.UUID] | None, Query()] = None,
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
) -> list[DocumentGraphSearchResult]:
    if not _INTERNAL_TOKEN or x_internal_token != _INTERNAL_TOKEN:
        raise HTTPException(status_code=403, detail="Internal token invalido")
    async with async_session_factory() as session:
        return await search_document_graph(session, q, limit, repo_id)


def _query_terms(q: str) -> list[str]:
    terms: list[str] = []
    for raw in _WORD_RE.findall(q):
        value = raw.strip().strip("`")
        if "." in value or len(value) >= 4:
            terms.append(value)
        if value.lower().startswith(("tg", "te", "tp")) and "." not in value:
            terms.append(f"dbo.{value}")
    return list(dict.fromkeys(terms))[:12]


def _score_node(node: DocumentGraphNode, terms: list[str]) -> float:
    name = node.name.lower()
    score = 0.5
    for term in terms:
        term_lower = term.lower()
        if name == term_lower:
            score += 1.0
        elif term_lower in name:
            score += 0.25
    return score
