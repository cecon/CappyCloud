"""Agents HTTP router — CRUD de perfis de agente (system prompts)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import get_authenticated_user, get_db_session
from app.domain.entities import User
from app.infrastructure.orm_models import Agent, Skill
from app.schemas import AgentCreate, AgentOut, AgentUpdate

router = APIRouter(prefix="/agents", tags=["agents"])


def _to_out(agent: Agent, skills_count: int = 0) -> AgentOut:
    return AgentOut(
        id=agent.id,
        slug=agent.slug,
        name=agent.name,
        description=agent.description,
        icon=agent.icon,
        system_prompt=agent.system_prompt,
        default_model=agent.default_model,
        active=agent.active,
        skills_count=skills_count,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


@router.get("", response_model=list[AgentOut])
async def list_agents(
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[AgentOut]:
    rows = await session.execute(select(Agent).order_by(Agent.name))
    agents = list(rows.scalars())
    if not agents:
        return []
    counts = await session.execute(
        select(Skill.agent_id, func.count(Skill.id))
        .where(Skill.agent_id.in_([a.id for a in agents]))
        .group_by(Skill.agent_id)
    )
    counts_map = {aid: c for aid, c in counts.all()}
    return [_to_out(a, counts_map.get(a.id, 0)) for a in agents]


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(
    agent_id: uuid.UUID,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentOut:
    agent = await session.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    count = await session.scalar(select(func.count(Skill.id)).where(Skill.agent_id == agent.id))
    return _to_out(agent, count or 0)


@router.post("", response_model=AgentOut, status_code=201)
async def create_agent(
    body: AgentCreate,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentOut:
    existing = await session.scalar(select(Agent).where(Agent.slug == body.slug))
    if existing:
        raise HTTPException(status_code=409, detail=f"Slug '{body.slug}' já existe")
    agent = Agent(
        id=uuid.uuid4(),
        slug=body.slug,
        name=body.name,
        description=body.description,
        icon=body.icon,
        system_prompt=body.system_prompt,
        default_model=body.default_model,
        active=body.active,
    )
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    return _to_out(agent)


@router.patch("/{agent_id}", response_model=AgentOut)
async def update_agent(
    agent_id: uuid.UUID,
    body: AgentUpdate,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentOut:
    agent = await session.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(agent, field, value)
    await session.commit()
    await session.refresh(agent)
    count = await session.scalar(select(func.count(Skill.id)).where(Skill.agent_id == agent.id))
    return _to_out(agent, count or 0)


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: uuid.UUID,
    _current: Annotated[User, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    agent = await session.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    await session.delete(agent)
    await session.commit()
