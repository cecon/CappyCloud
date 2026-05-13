"""SQLAlchemy implementation of AttachmentRepository port."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import MessageAttachment as AttachEntity
from app.infrastructure.orm_models import MessageAttachment as AttachORM
from app.ports.repositories import AttachmentRepository


class SQLAlchemyAttachmentRepository(AttachmentRepository):
    """Concrete AttachmentRepository backed by PostgreSQL via SQLAlchemy async."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, attachment: AttachEntity) -> AttachEntity:
        orm = AttachORM(
            id=attachment.id,
            conversation_id=attachment.conversation_id,
            message_id=attachment.message_id,
            kind=attachment.kind,
            mime_type=attachment.mime_type,
            storage_path=attachment.storage_path,
            original_filename=attachment.original_filename,
            size_bytes=attachment.size_bytes,
            vision_description=attachment.vision_description,
            vision_model_used=attachment.vision_model_used,
            uploaded_by=attachment.uploaded_by,
        )
        self._session.add(orm)
        await self._session.commit()
        await self._session.refresh(orm)
        return self._to_entity(orm)

    async def get(
        self, attachment_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> AttachEntity | None:
        row = (
            await self._session.execute(
                select(AttachORM)
                .where(AttachORM.id == attachment_id)
                .where(AttachORM.conversation_id == conversation_id)
                .limit(1)
            )
        ).scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def list_by_ids(
        self, attachment_ids: list[uuid.UUID], conversation_id: uuid.UUID
    ) -> list[AttachEntity]:
        if not attachment_ids:
            return []
        result = await self._session.execute(
            select(AttachORM)
            .where(AttachORM.conversation_id == conversation_id)
            .where(AttachORM.id.in_(attachment_ids))
            .order_by(AttachORM.uploaded_at.asc())
        )
        return [self._to_entity(row) for row in result.scalars().all()]

    async def delete(self, attachment_id: uuid.UUID, conversation_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            delete(AttachORM)
            .where(AttachORM.id == attachment_id)
            .where(AttachORM.conversation_id == conversation_id)
        )
        await self._session.commit()
        # rowcount existe em CursorResult retornado por DML (delete/update)
        # mas o tipo estático é Result[Any] — getattr seguro evita o falso erro.
        return int(getattr(result, "rowcount", 0) or 0) > 0

    async def update_description(
        self,
        attachment_id: uuid.UUID,
        description: str,
        model_used: str,
    ) -> None:
        await self._session.execute(
            update(AttachORM)
            .where(AttachORM.id == attachment_id)
            .values(
                vision_description=description,
                vision_model_used=model_used,
            )
        )
        await self._session.commit()

    @staticmethod
    def _to_entity(row: AttachORM) -> AttachEntity:
        return AttachEntity(
            id=row.id,
            conversation_id=row.conversation_id,
            message_id=row.message_id,
            kind=row.kind,
            mime_type=row.mime_type,
            storage_path=row.storage_path,
            original_filename=row.original_filename,
            size_bytes=row.size_bytes or 0,
            vision_description=row.vision_description,
            vision_model_used=row.vision_model_used,
            uploaded_by=row.uploaded_by,
            uploaded_at=row.uploaded_at,
        )
