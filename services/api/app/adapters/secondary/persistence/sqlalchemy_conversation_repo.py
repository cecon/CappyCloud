"""SQLAlchemy implementation of ConversationRepository port."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Conversation as ConvEntity
from app.domain.value_objects import validate_permission_mode
from app.infrastructure.orm_models import Conversation as ConvORM
from app.infrastructure.orm_models import User as UserORM
from app.ports.repositories import ConversationRepository


class SQLAlchemyConversationRepository(ConversationRepository):
    """Concrete ConversationRepository backed by PostgreSQL via SQLAlchemy async."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_user(self, user_id: uuid.UUID) -> list[ConvEntity]:
        result = await self._session.execute(
            select(ConvORM).where(ConvORM.user_id == user_id).order_by(ConvORM.updated_at.desc())
        )
        return [self._to_entity(row) for row in result.scalars().all()]

    async def list_all(self) -> list[ConvEntity]:
        result = await self._session.execute(
            select(ConvORM, UserORM.email)
            .outerjoin(UserORM, UserORM.id == ConvORM.user_id)
            .order_by(ConvORM.updated_at.desc())
        )
        return [self._to_entity(row, user_email=email) for row, email in result.all()]

    async def get(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> ConvEntity | None:
        result = await self._session.execute(
            select(ConvORM).where(
                ConvORM.id == conversation_id,
                ConvORM.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def save(self, conversation: ConvEntity) -> ConvEntity:
        orm = ConvORM(
            id=conversation.id,
            user_id=conversation.user_id,
            title=conversation.title,
            sandbox_id=conversation.sandbox_id,
            ai_model_id=conversation.ai_model_id,
            repos=conversation.repos,
            session_root=conversation.session_root,
            permission_mode=validate_permission_mode(conversation.permission_mode),
        )
        self._session.add(orm)
        await self._session.commit()
        await self._session.refresh(orm)
        return self._to_entity(orm)

    async def update(self, conversation: ConvEntity) -> ConvEntity:
        result = await self._session.execute(select(ConvORM).where(ConvORM.id == conversation.id))
        orm = result.scalar_one()
        orm.title = conversation.title
        orm.sandbox_id = conversation.sandbox_id
        orm.ai_model_id = conversation.ai_model_id
        orm.repos = conversation.repos
        orm.session_root = conversation.session_root
        orm.permission_mode = validate_permission_mode(conversation.permission_mode)
        await self._session.commit()
        await self._session.refresh(orm)
        return self._to_entity(orm)

    @staticmethod
    def _to_entity(row: ConvORM, user_email: str | None = None) -> ConvEntity:
        return ConvEntity(
            id=row.id,
            user_id=row.user_id,
            title=row.title,
            created_at=row.created_at,
            updated_at=row.updated_at,
            sandbox_id=row.sandbox_id,
            ai_model_id=row.ai_model_id,
            repos=row.repos or [],
            session_root=row.session_root,
            permission_mode=validate_permission_mode(getattr(row, "permission_mode", None)),
            worktree_exists=row.worktree_exists,
            lines_added=row.lines_added,
            lines_removed=row.lines_removed,
            files_changed=row.files_changed,
            pr_url=row.pr_url,
            pr_status=row.pr_status,
            pr_approved=row.pr_approved,
            pr_number=row.github_pr_number,
            github_repo_slug=row.github_repo_slug,
            ci_status=row.ci_status,
            ci_url=row.ci_url,
            user_email=user_email,
        )
