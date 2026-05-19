"""Entity mappers for sandbox/global skill persistence."""

from __future__ import annotations

import uuid

from app.domain.entities import GlobalSkill, SandboxSkill
from app.infrastructure.orm_models_sandbox_globals import (
    GlobalSkill as GlobalSkillORM,
)
from app.infrastructure.orm_models_sandbox_globals import (
    SandboxSkill as SandboxSkillORM,
)


def global_skill_to_entity(orm: GlobalSkillORM, sandbox_ids: list[uuid.UUID]) -> GlobalSkill:
    return GlobalSkill(
        id=orm.id,
        name=orm.name,
        description=orm.description or "",
        content=orm.content or "",
        enabled=orm.enabled,
        sandbox_ids=list(sandbox_ids),
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def global_skill_to_sandbox_entity(orm: GlobalSkillORM, sandbox_id: uuid.UUID) -> SandboxSkill:
    return SandboxSkill(
        id=orm.id,
        sandbox_id=sandbox_id,
        name=orm.name,
        description=orm.description or "",
        content=orm.content or "",
        enabled=orm.enabled,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def global_entity_to_sandbox_entity(skill: GlobalSkill, sandbox_id: uuid.UUID) -> SandboxSkill:
    return SandboxSkill(
        id=skill.id,
        sandbox_id=sandbox_id,
        name=skill.name,
        description=skill.description,
        content=skill.content,
        enabled=skill.enabled,
        created_at=skill.created_at,
        updated_at=skill.updated_at,
    )


def legacy_skill_to_entity(orm: SandboxSkillORM) -> SandboxSkill:
    return SandboxSkill(
        id=orm.id,
        sandbox_id=orm.sandbox_id,
        name=orm.name,
        description=orm.description or "",
        content=orm.content or "",
        enabled=orm.enabled,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )
