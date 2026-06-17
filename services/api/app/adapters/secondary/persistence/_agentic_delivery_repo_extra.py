"""Extra SQLAlchemy methods for agentic delivery repository."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.agentic_delivery import AgenticPermissionValue
from app.infrastructure import orm_models_agentic_delivery as orm
from app.ports.agentic_delivery import Page


class AgenticDeliveryRepositoryExtraMixin:
    _session: AsyncSession

    def _row(self, row: Any) -> dict:
        raise NotImplementedError

    async def _page(self, stmt: Any, limit: int, cursor: str | None) -> Page:
        raise NotImplementedError

    async def list_sensitive_surfaces(
        self,
        repository_id: uuid.UUID | None,
        domain_key: str | None,
        limit: int,
        cursor: str | None,
    ) -> Page:
        stmt = select(orm.SensitiveSurface).where(orm.SensitiveSurface.active.is_(True))
        if repository_id:
            stmt = stmt.where(
                or_(
                    orm.SensitiveSurface.repository_id == repository_id,
                    orm.SensitiveSurface.repository_id.is_(None),
                )
            )
        if domain_key:
            stmt = stmt.where(
                or_(
                    orm.SensitiveSurface.domain_key == domain_key,
                    orm.SensitiveSurface.domain_key.is_(None),
                )
            )
        return await self._page(stmt.order_by(orm.SensitiveSurface.created_at), limit, cursor)

    async def save_sensitive_surface(self, surface_id: uuid.UUID, body: dict) -> dict:
        row = await self._session.get(orm.SensitiveSurface, surface_id)
        if row is None:
            row = orm.SensitiveSurface(id=surface_id, **body)
            self._session.add(row)
        else:
            for key, value in body.items():
                setattr(row, key, value)
        await self._session.commit()
        await self._session.refresh(row)
        return self._row(row)

    async def search_knowledge(
        self,
        repository_ids: list[uuid.UUID],
        domain_key: str | None,
        query: str,
        limit: int,
        cursor: str | None,
    ) -> Page:
        stmt = select(orm.ReusableKnowledgeItem).where(
            orm.ReusableKnowledgeItem.active.is_(True),
            orm.ReusableKnowledgeItem.repository_id.in_(repository_ids),
        )
        if domain_key:
            stmt = stmt.where(
                or_(
                    orm.ReusableKnowledgeItem.domain_key == domain_key,
                    orm.ReusableKnowledgeItem.domain_key.is_(None),
                )
            )
        if query.strip():
            term = f"%{query.strip()}%"
            stmt = stmt.where(
                or_(
                    orm.ReusableKnowledgeItem.title.ilike(term),
                    orm.ReusableKnowledgeItem.content.ilike(term),
                )
            )
        return await self._page(
            stmt.order_by(orm.ReusableKnowledgeItem.created_at.desc()), limit, cursor
        )

    async def create_knowledge_relationship(self, body: dict) -> dict:
        row = orm.KnowledgeReuseRelationship(id=uuid.uuid4(), **body)
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return self._row(row)

    async def upsert_permission(
        self,
        permission_id: uuid.UUID,
        user_id: uuid.UUID,
        granted_by_user_id: uuid.UUID,
        permission: AgenticPermissionValue,
        active: bool,
        repository_id: uuid.UUID | None = None,
        domain_key: str | None = None,
    ) -> dict:
        row = await self._session.get(orm.AgenticDeliveryPermission, permission_id)
        values = {
            "user_id": user_id,
            "repository_id": repository_id,
            "domain_key": domain_key,
            "permission": permission.value,
            "granted_by_user_id": granted_by_user_id,
            "active": active,
        }
        if row is None:
            row = orm.AgenticDeliveryPermission(id=permission_id, **values)
            self._session.add(row)
        else:
            for key, value in values.items():
                setattr(row, key, value)
        await self._session.commit()
        await self._session.refresh(row)
        return self._row(row)

    async def has_permission(
        self,
        user_id: uuid.UUID,
        permission: AgenticPermissionValue,
        repository_id: uuid.UUID | None,
        domain_key: str | None,
    ) -> bool:
        stmt = select(orm.AgenticDeliveryPermission.id).where(
            orm.AgenticDeliveryPermission.user_id == user_id,
            orm.AgenticDeliveryPermission.permission == permission.value,
            orm.AgenticDeliveryPermission.active.is_(True),
        )
        if repository_id:
            stmt = stmt.where(
                or_(
                    orm.AgenticDeliveryPermission.repository_id == repository_id,
                    orm.AgenticDeliveryPermission.repository_id.is_(None),
                )
            )
        if domain_key:
            stmt = stmt.where(
                or_(
                    orm.AgenticDeliveryPermission.domain_key == domain_key,
                    orm.AgenticDeliveryPermission.domain_key.is_(None),
                )
            )
        result = await self._session.execute(stmt.limit(1))
        return result.scalar_one_or_none() is not None

    async def authorize_external_action(self, body: dict) -> dict:
        row = orm.ExternalActionAuthorization(id=uuid.uuid4(), **body)
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return self._row(row)

    async def list_metrics(self, cycle_id: uuid.UUID, limit: int, cursor: str | None) -> Page:
        return await self._page(
            select(orm.CycleMetric)
            .where(orm.CycleMetric.cycle_id == cycle_id)
            .order_by(orm.CycleMetric.created_at, orm.CycleMetric.id),
            limit,
            cursor,
        )

    async def upsert_metric(
        self,
        cycle_id: uuid.UUID,
        name: str,
        value: float | None,
        unit: str,
        source: str,
        text: str | None = None,
    ) -> dict:
        row = orm.CycleMetric(
            id=uuid.uuid4(),
            cycle_id=cycle_id,
            metric_name=name,
            metric_value=value,
            metric_text=text,
            metric_unit=unit,
            source=source,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return self._row(row)
