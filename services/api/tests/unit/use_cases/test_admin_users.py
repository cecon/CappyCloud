"""Unit tests for admin_users use cases (ADR-005)."""

from __future__ import annotations

import uuid

import pytest
from app.application.use_cases.admin_users import (
    CannotDemoteSelfError,
    ListUsers,
    UpdateUserRole,
    UserNotFoundError,
)
from app.domain.entities import User, UserRole

from tests.conftest import InMemoryUserRepository


async def _seed(repo: InMemoryUserRepository, email: str, role: UserRole) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password="hashed:password123",
        role=role,
    )
    return await repo.save(user)


class TestListUsers:
    async def test_returns_empty_when_no_users(self) -> None:
        repo = InMemoryUserRepository()
        result = await ListUsers(repo).execute()
        assert result == []

    async def test_returns_users_ordered_by_created_at(self) -> None:
        repo = InMemoryUserRepository()
        u1 = await _seed(repo, "first@x.com", UserRole.ADMIN)
        u2 = await _seed(repo, "second@x.com", UserRole.USER)

        result = await ListUsers(repo).execute()

        # Mesmo conjunto, ordem cronológica (asserts específicos, sobrevive mutação):
        assert [u.id for u in result] == [u1.id, u2.id]
        assert result[0].role is UserRole.ADMIN
        assert result[1].role is UserRole.USER


class TestUpdateUserRole:
    async def test_promotes_user_to_admin(self) -> None:
        repo = InMemoryUserRepository()
        admin = await _seed(repo, "admin@x.com", UserRole.ADMIN)
        target = await _seed(repo, "target@x.com", UserRole.USER)

        updated = await UpdateUserRole(repo).execute(
            target.id, UserRole.ADMIN, acting_user_id=admin.id
        )

        assert updated.role is UserRole.ADMIN
        # Persistido no repo, não só devolvido:
        reread = await repo.get_by_id(target.id)
        assert reread is not None and reread.is_admin

    async def test_demotes_other_admin_to_user(self) -> None:
        repo = InMemoryUserRepository()
        me = await _seed(repo, "me@x.com", UserRole.ADMIN)
        other_admin = await _seed(repo, "other@x.com", UserRole.ADMIN)

        updated = await UpdateUserRole(repo).execute(
            other_admin.id, UserRole.USER, acting_user_id=me.id
        )

        assert updated.role is UserRole.USER

    async def test_cannot_demote_self(self) -> None:
        repo = InMemoryUserRepository()
        me = await _seed(repo, "me@x.com", UserRole.ADMIN)

        with pytest.raises(CannotDemoteSelfError, match="rebaixar a si mesmo"):
            await UpdateUserRole(repo).execute(me.id, UserRole.USER, acting_user_id=me.id)

        # Estado inalterado — defesa em profundidade:
        reread = await repo.get_by_id(me.id)
        assert reread is not None and reread.is_admin

    async def test_self_promote_admin_to_admin_is_noop_pass(self) -> None:
        # Auto-mudança permitida quando o papel de destino é ADMIN — não rebaixa.
        repo = InMemoryUserRepository()
        me = await _seed(repo, "me@x.com", UserRole.ADMIN)

        updated = await UpdateUserRole(repo).execute(me.id, UserRole.ADMIN, acting_user_id=me.id)

        assert updated.role is UserRole.ADMIN

    async def test_unknown_user_raises(self) -> None:
        repo = InMemoryUserRepository()
        me = await _seed(repo, "me@x.com", UserRole.ADMIN)

        with pytest.raises(UserNotFoundError, match="não encontrado"):
            await UpdateUserRole(repo).execute(uuid.uuid4(), UserRole.ADMIN, acting_user_id=me.id)
