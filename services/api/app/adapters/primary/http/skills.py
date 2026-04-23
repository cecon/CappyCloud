"""Skills HTTP router — CRUD e import por URL.

A busca (autenticada e interna) está em ``skills_search.py``.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import get_authenticated_user, get_db_session
from app.domain.entities import User
from app.infrastructure.embeddings import embed_text
from app.infrastructure.orm_models import Agent, Skill
from app.infrastructure.skill_importer import ImporterError, import_url
from app.schemas import SkillCreate, SkillImportFromUrlBody, SkillOut, SkillUpdate

router = APIRouter(prefix="/skills", tags=["skills"])
log = logging.getLogger(__name__)


def _slugify(text: str, max_len: int = 80) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:max_len] or "skill"


def _to_out(skill: Skill) -> SkillOut:
    return SkillOut(
        id=skill.id,
        agent_id=skill.agent_id,
        slug=skill.slug,
        title=skill.title,
        summary=skill.summary,
        content=skill.content,
        tags=list(skill.tags or []),
        source_url=skill.source_url,
        active=skill.active,
        has_embedding=skill.embedding is not None,
        created_at=skill.created_at,
        updated_at=skill.updated_at,
    )


async def _ensure_unique_slug(
    session: AsyncSession, base_slug: str, exclude_id: uuid.UUID | None = None
) -> str:
    """Devolve um slug único na tabela ``skills``, anexando -2, -3… se necessário."""
    candidate = base_slug
    suffix = 2
    while True:
        q = select(Skill).where(Skill.slug == candidate)
        if exclude_id:
            q = q.where(Skill.id != exclude_id)
        existing = await session.scalar(q)
        if not existing:
            return candidate
        candidate = f"{base_slug}-{suffix}"
        suffix += 1


async def _set_embedding(skill: Skill) -> None:
    """Calcula e atribui o embedding para uma skill (silencioso em caso de erro)."""
    text_for_embed = f"{skill.title}\n\n{skill.summary}\n\n{skill.content}"[:8000]
    try:
        emb = await embed_text(text_for_embed)
        if emb:
            skill.embedding = emb
    except Exception as exc:
        log.warning("Falha a calcular embedding para skill %s: %s", skill.slug, exc)


@router.get("", response_model=list[SkillOut])
async def list_skills(
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    agent_id: uuid.UUID | None = Query(default=None),  # noqa: B008
    active: bool | None = Query(default=None),
) -> list[SkillOut]:
    q = select(Skill).order_by(Skill.title)
    if agent_id is not None:
        q = q.where(Skill.agent_id == agent_id)
    if active is not None:
        q = q.where(Skill.active.is_(active))
    rows = await session.execute(q)
    return [_to_out(s) for s in rows.scalars()]


@router.get("/{skill_id}", response_model=SkillOut)
async def get_skill(
    skill_id: uuid.UUID,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SkillOut:
    skill = await session.get(Skill, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill não encontrada")
    return _to_out(skill)


@router.post("", response_model=SkillOut, status_code=201)
async def create_skill(
    body: SkillCreate,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SkillOut:
    if body.agent_id is not None:
        agent = await session.get(Agent, body.agent_id)
        if not agent:
            raise HTTPException(status_code=400, detail="agent_id inválido")
    base_slug = body.slug or _slugify(body.title)
    slug = await _ensure_unique_slug(session, base_slug)
    skill = Skill(
        id=uuid.uuid4(),
        agent_id=body.agent_id,
        slug=slug,
        title=body.title,
        summary=body.summary,
        content=body.content,
        tags=body.tags,
        source_url=body.source_url,
        active=True,
    )
    await _set_embedding(skill)
    session.add(skill)
    await session.commit()
    await session.refresh(skill)
    return _to_out(skill)


@router.patch("/{skill_id}", response_model=SkillOut)
async def update_skill(
    skill_id: uuid.UUID,
    body: SkillUpdate,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SkillOut:
    skill = await session.get(Skill, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill não encontrada")
    changes = body.model_dump(exclude_unset=True)
    if changes.get("agent_id") is not None:
        agent = await session.get(Agent, changes["agent_id"])
        if not agent:
            raise HTTPException(status_code=400, detail="agent_id inválido")
    for field, value in changes.items():
        setattr(skill, field, value)
    if any(k in changes for k in ("title", "summary", "content")):
        await _set_embedding(skill)
    await session.commit()
    await session.refresh(skill)
    return _to_out(skill)


@router.delete("/{skill_id}", status_code=204)
async def delete_skill(
    skill_id: uuid.UUID,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    skill = await session.get(Skill, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill não encontrada")
    await session.delete(skill)
    await session.commit()


@router.post("/import-url", response_model=SkillOut, status_code=201)
async def import_skill_from_url(
    body: SkillImportFromUrlBody,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SkillOut:
    if body.agent_id is not None:
        agent = await session.get(Agent, body.agent_id)
        if not agent:
            raise HTTPException(status_code=400, detail="agent_id inválido")
    try:
        extracted = await import_url(body.url)
    except ImporterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    slug = await _ensure_unique_slug(session, extracted["slug"])
    skill = Skill(
        id=uuid.uuid4(),
        agent_id=body.agent_id,
        slug=slug,
        title=extracted["title"],
        summary=extracted["summary"],
        content=extracted["content"],
        tags=body.tags,
        source_url=extracted["source_url"],
        active=True,
    )
    await _set_embedding(skill)
    session.add(skill)
    await session.commit()
    await session.refresh(skill)
    return _to_out(skill)
