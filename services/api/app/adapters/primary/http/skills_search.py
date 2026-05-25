"""Busca de Skills (RAG híbrida) — endpoints público (JWT) e interno (token sandbox)."""

from __future__ import annotations

import os
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import get_authenticated_user, get_db_session
from app.domain.entities import User
from app.infrastructure.database import async_session_factory
from app.infrastructure.embeddings import embed_text
from app.infrastructure.orm_models import Skill
from app.schemas import SkillSearchResult

router = APIRouter(prefix="/skills", tags=["skills"])

_INTERNAL_TOKEN = os.getenv("INTERNAL_API_TOKEN", "").strip()
_SKILL_SUMMARY_LIMIT = 300
_DOCUMENT_SUMMARY_LIMIT = 2000


def _row_to_result(skill: Skill, score: float) -> SkillSearchResult:
    return SkillSearchResult(
        id=skill.id,
        slug=skill.slug,
        title=skill.title,
        summary=_result_summary(skill),
        score=score,
        source_url=skill.source_url,
    )


def _result_summary(skill: Skill) -> str:
    if skill.document_id is not None:
        return (skill.content or skill.summary or "")[:_DOCUMENT_SUMMARY_LIMIT]
    return (skill.summary or skill.content or "")[:_SKILL_SUMMARY_LIMIT]


async def do_search(
    session: AsyncSession,
    q: str,
    limit: int,
    repo_ids: list[uuid.UUID] | None = None,
) -> list[SkillSearchResult]:
    """Busca híbrida: vetorial (cosine) se houver embedding; senão lexical (ILIKE)."""
    query_emb = await embed_text(q)
    filters: list = [Skill.active.is_(True)]
    if repo_ids:
        filters.append(Skill.repository_id.in_(repo_ids))

    if query_emb is not None:
        distance = Skill.embedding.cosine_distance(query_emb)
        rows = await session.execute(
            select(Skill, distance.label("dist"))
            .where(*filters, Skill.embedding.is_not(None))
            .order_by("dist")
            .limit(limit)
        )
        out = [_row_to_result(s, max(0.0, 1.0 - float(d))) for s, d in rows.all()]
        if out:
            return out

    pattern = f"%{q}%"
    rows = await session.execute(
        select(Skill)
        .where(
            *filters,
            or_(
                Skill.title.ilike(pattern),
                Skill.summary.ilike(pattern),
                Skill.content.ilike(pattern),
            ),
        )
        .order_by(Skill.title)
        .limit(limit)
    )
    return [_row_to_result(s, 0.5) for s in rows.scalars()]


@router.get("/_search/run", response_model=list[SkillSearchResult])
async def search_skills(
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    q: str = Query(min_length=1, max_length=512),
    limit: int = Query(default=5, ge=1, le=20),
    repo_id: Annotated[list[uuid.UUID] | None, Query()] = None,
) -> list[SkillSearchResult]:
    """Busca de Skills (autenticada por JWT)."""
    return await do_search(session, q, limit, repo_id)


@router.get("/_search/internal", response_model=list[SkillSearchResult])
async def search_skills_internal(
    q: str = Query(min_length=1, max_length=512),
    limit: int = Query(default=5, ge=1, le=20),
    repo_id: Annotated[list[uuid.UUID] | None, Query()] = None,
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
) -> list[SkillSearchResult]:
    """Endpoint interno usado pelo sandbox para o LLM consultar skills via Bash.

    Não requer JWT — autentica por ``X-Internal-Token`` que tem de bater com a env
    ``INTERNAL_API_TOKEN`` (configurada no docker-compose).
    """
    if not _INTERNAL_TOKEN or x_internal_token != _INTERNAL_TOKEN:
        raise HTTPException(status_code=403, detail="Internal token inválido")
    async with async_session_factory() as session:
        return await do_search(session, q, limit, repo_id)
