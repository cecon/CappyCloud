"""Use cases for reusable knowledge."""

from __future__ import annotations

import uuid

from app.domain.entities import UserRole
from app.ports.agentic_delivery import AgenticDeliveryAuditPort, AgenticDeliveryRepository
from app.ports.user_access import UserRepositoryAccessRepository


class SearchReusableKnowledge:
    def __init__(
        self,
        repo: AgenticDeliveryRepository,
        access: UserRepositoryAccessRepository,
        audit: AgenticDeliveryAuditPort | None = None,
    ) -> None:
        self._repo = repo
        self._access = access
        self._audit = audit

    async def execute(
        self,
        user_id: uuid.UUID,
        user_role: UserRole,
        repository_ids: list[uuid.UUID],
        domain_key: str | None,
        query: str,
        limit: int,
        cursor: str | None,
    ) -> dict:
        allowed = await self._allowed_repositories(user_id, user_role, repository_ids)
        denied = sorted(set(repository_ids) - set(allowed))
        if denied and self._audit:
            await self._audit.record(
                "agentic_delivery.knowledge_denied",
                {"repositories": [str(r) for r in denied]},
            )
        page = await self._repo.search_knowledge(allowed, domain_key, query, limit, cursor)
        return {
            "items": [self._mark_evidence_state(item) for item in page.items],
            "next_cursor": page.next_cursor,
        }

    @staticmethod
    def _mark_evidence_state(item: dict) -> dict:
        evidence_ids = item.get("evidence_source_ids") or []
        evidence_state = str(item.get("evidence_status") or "").lower()
        unavailable = evidence_state in {"stale", "unavailable", "unsupported"}
        needs_review = bool(item.get("needs_review") or unavailable or not evidence_ids)
        return dict(item, needs_review=needs_review)

    async def _allowed_repositories(
        self, user_id: uuid.UUID, user_role: UserRole, repository_ids: list[uuid.UUID]
    ) -> list[uuid.UUID]:
        if user_role is UserRole.ADMIN:
            return repository_ids
        allowed: list[uuid.UUID] = []
        for repo_id in repository_ids:
            if await self._access.has_access(user_id, repo_id):
                allowed.append(repo_id)
        return allowed


class CreateKnowledgeReuseRelationship:
    def __init__(self, repo: AgenticDeliveryRepository) -> None:
        self._repo = repo

    async def execute(self, body: dict) -> dict:
        return await self._repo.create_knowledge_relationship(body)
