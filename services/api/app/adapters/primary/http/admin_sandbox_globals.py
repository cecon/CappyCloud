"""HTTP adapter administrativo para skills e agents globais por sandbox (ADR-004)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.primary.http.deps import require_role
from app.adapters.primary.http.deps_base import get_db_session
from app.adapters.secondary.persistence.sqlalchemy_sandbox_globals_repo import (
    SQLAlchemySandboxAgentRepository,
    SQLAlchemySandboxSkillRepository,
)
from app.application.use_cases.sandbox_globals import (
    CreateSandboxAgent,
    CreateSandboxSkill,
    DeleteSandboxAgent,
    DeleteSandboxSkill,
    ListSandboxAgents,
    ListSandboxSkills,
    SandboxGlobalNameTakenError,
    SandboxGlobalNotFoundError,
    UpdateSandboxAgent,
    UpdateSandboxSkill,
)
from app.domain.entities import UserRole
from app.ports.sandbox_globals import SandboxAgentRepository, SandboxSkillRepository
from app.schemas_sandbox_globals import (
    SandboxAgentCreate,
    SandboxAgentOut,
    SandboxAgentUpdate,
    SandboxSkillCreate,
    SandboxSkillOut,
    SandboxSkillUpdate,
)


def get_skill_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SandboxSkillRepository:
    return SQLAlchemySandboxSkillRepository(session)


def get_agent_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SandboxAgentRepository:
    return SQLAlchemySandboxAgentRepository(session)


skills_router = APIRouter(
    prefix="/admin/sandboxes/{sandbox_id}/skills",
    tags=["admin"],
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
agents_router = APIRouter(
    prefix="/admin/sandboxes/{sandbox_id}/agents",
    tags=["admin"],
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)


# ── Skills ───────────────────────────────────────────────────────────────────


@skills_router.get("", response_model=list[SandboxSkillOut])
async def list_skills(
    sandbox_id: uuid.UUID,
    repo: Annotated[SandboxSkillRepository, Depends(get_skill_repo)],
) -> list[SandboxSkillOut]:
    rows = await ListSandboxSkills(repo).execute(sandbox_id)
    return [SandboxSkillOut.model_validate(s.__dict__) for s in rows]


@skills_router.post(
    "",
    response_model=SandboxSkillOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_skill(
    sandbox_id: uuid.UUID,
    body: SandboxSkillCreate,
    repo: Annotated[SandboxSkillRepository, Depends(get_skill_repo)],
) -> SandboxSkillOut:
    try:
        skill = await CreateSandboxSkill(repo).execute(
            sandbox_id=sandbox_id,
            name=body.name,
            description=body.description,
            content=body.content,
            enabled=body.enabled,
        )
    except SandboxGlobalNameTakenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SandboxSkillOut.model_validate(skill.__dict__)


@skills_router.put("/{skill_id}", response_model=SandboxSkillOut)
async def update_skill(
    sandbox_id: uuid.UUID,
    skill_id: uuid.UUID,
    body: SandboxSkillUpdate,
    repo: Annotated[SandboxSkillRepository, Depends(get_skill_repo)],
) -> SandboxSkillOut:
    try:
        skill = await UpdateSandboxSkill(repo).execute(
            skill_id=skill_id,
            sandbox_id=sandbox_id,
            name=body.name,
            description=body.description,
            content=body.content,
            enabled=body.enabled,
        )
    except SandboxGlobalNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SandboxGlobalNameTakenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SandboxSkillOut.model_validate(skill.__dict__)


@skills_router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    sandbox_id: uuid.UUID,
    skill_id: uuid.UUID,
    repo: Annotated[SandboxSkillRepository, Depends(get_skill_repo)],
) -> None:
    deleted = await DeleteSandboxSkill(repo).execute(skill_id, sandbox_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill não encontrada.")


# ── Agents ───────────────────────────────────────────────────────────────────


@agents_router.get("", response_model=list[SandboxAgentOut])
async def list_agents(
    sandbox_id: uuid.UUID,
    repo: Annotated[SandboxAgentRepository, Depends(get_agent_repo)],
) -> list[SandboxAgentOut]:
    rows = await ListSandboxAgents(repo).execute(sandbox_id)
    return [SandboxAgentOut.model_validate(a.__dict__) for a in rows]


@agents_router.post(
    "",
    response_model=SandboxAgentOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_agent(
    sandbox_id: uuid.UUID,
    body: SandboxAgentCreate,
    repo: Annotated[SandboxAgentRepository, Depends(get_agent_repo)],
) -> SandboxAgentOut:
    try:
        agent = await CreateSandboxAgent(repo).execute(
            sandbox_id=sandbox_id,
            name=body.name,
            description=body.description,
            system_prompt=body.system_prompt,
            model=body.model,
            tools=body.tools,
            enabled=body.enabled,
        )
    except SandboxGlobalNameTakenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SandboxAgentOut.model_validate(agent.__dict__)


@agents_router.put("/{agent_id}", response_model=SandboxAgentOut)
async def update_agent(
    sandbox_id: uuid.UUID,
    agent_id: uuid.UUID,
    body: SandboxAgentUpdate,
    repo: Annotated[SandboxAgentRepository, Depends(get_agent_repo)],
) -> SandboxAgentOut:
    try:
        agent = await UpdateSandboxAgent(repo).execute(
            agent_id=agent_id,
            sandbox_id=sandbox_id,
            name=body.name,
            description=body.description,
            system_prompt=body.system_prompt,
            model=body.model,
            tools=body.tools,
            enabled=body.enabled,
        )
    except SandboxGlobalNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SandboxGlobalNameTakenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SandboxAgentOut.model_validate(agent.__dict__)


@agents_router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    sandbox_id: uuid.UUID,
    agent_id: uuid.UUID,
    repo: Annotated[SandboxAgentRepository, Depends(get_agent_repo)],
) -> None:
    deleted = await DeleteSandboxAgent(repo).execute(agent_id, sandbox_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent não encontrado.")
