"""Escopo de admin: ADMIN global vs admin de workspace (regras puras, sem banco)."""

from __future__ import annotations

import uuid

import pytest
from app.application.use_cases.admin_scope import (
    AdminScope,
    AdminScopeDeniedError,
    ResolveAdminScope,
    ensure_can_grant,
    ensure_can_revoke,
    ensure_manageable_user,
)
from app.application.use_cases.auth import RegisterUser
from app.application.use_cases.workspace_members import AddWorkspaceMember, ListScopedUsers
from app.domain.entities import User, UserRole

from tests.conftest import FakePasswordService, InMemoryUserRepository
from tests.fakes_workspace_admin import InMemoryWorkspaceAdminRepository

PROTHEUS = uuid.uuid4()
OUTRO = uuid.uuid4()


def _user(email: str, role: UserRole = UserRole.USER, *, super_admin: bool = False) -> User:
    return User(
        id=uuid.uuid4(), email=email, hashed_password="x", role=role, is_super_admin=super_admin
    )


@pytest.fixture
def setup() -> tuple[InMemoryUserRepository, InMemoryWorkspaceAdminRepository, dict[str, User]]:
    users = InMemoryUserRepository()
    access = InMemoryWorkspaceAdminRepository()
    people = {
        "rodolfo": _user("rodolfo@x.com"),
        "ana": _user("ana@x.com"),
        "bia": _user("bia@x.com"),
        "adm": _user("adm@x.com", UserRole.ADMIN),
    }
    for person in people.values():
        users._store[person.id] = person
    access.add(people["rodolfo"].id, PROTHEUS, admin=True)
    access.add(people["ana"].id, PROTHEUS)
    access.add(people["bia"].id, OUTRO)
    return users, access, people


async def test_resolve_global_admin_and_workspace_admin(setup) -> None:
    _, access, people = setup
    resolve = ResolveAdminScope(access)

    assert (await resolve.execute(people["adm"])).is_global
    scope = await resolve.execute(people["rodolfo"])
    assert scope.workspace_ids == frozenset({PROTHEUS})
    assert scope.allows(PROTHEUS) and not scope.allows(OUTRO) and not scope.allows(None)
    with pytest.raises(AdminScopeDeniedError):
        await resolve.execute(people["ana"])


async def test_workspace_admin_manages_only_plain_members(setup) -> None:
    _, access, people = setup
    scope = AdminScope(user=people["rodolfo"], workspace_ids=frozenset({PROTHEUS}))

    await ensure_manageable_user(scope, people["ana"], access)
    for target in ("bia", "adm", "rodolfo"):
        with pytest.raises(AdminScopeDeniedError):
            await ensure_manageable_user(scope, people[target], access)

    other_admin = _user("aleff@x.com")
    access.add(other_admin.id, PROTHEUS, admin=True)
    with pytest.raises(AdminScopeDeniedError):
        await ensure_manageable_user(scope, other_admin, access)


async def test_grant_and_revoke_rules(setup) -> None:
    _, _, people = setup
    scope = AdminScope(user=people["rodolfo"], workspace_ids=frozenset({PROTHEUS}))

    ensure_can_grant(scope, people["bia"], PROTHEUS)
    with pytest.raises(AdminScopeDeniedError):
        ensure_can_grant(scope, people["bia"], OUTRO)
    with pytest.raises(AdminScopeDeniedError):
        ensure_can_grant(scope, people["adm"], PROTHEUS)
    with pytest.raises(AdminScopeDeniedError):
        ensure_can_revoke(scope, people["ana"], PROTHEUS, target_is_admin=True)
    ensure_can_revoke(scope, people["ana"], PROTHEUS, target_is_admin=False)


async def test_list_scoped_users(setup) -> None:
    users, access, people = setup
    scope = AdminScope(user=people["rodolfo"], workspace_ids=frozenset({PROTHEUS}))

    listed = {u.email for u in await ListScopedUsers(users, access).execute(scope)}

    assert listed == {"rodolfo@x.com", "ana@x.com"}
    everyone = await ListScopedUsers(users, access).execute(
        AdminScope(user=people["adm"], workspace_ids=None)
    )
    assert len(everyone) == 4


async def test_add_member_creates_user_with_access_and_creator_models(setup) -> None:
    users, access, people = setup
    model = uuid.uuid4()
    access.models[people["rodolfo"].id] = {model}
    scope = AdminScope(user=people["rodolfo"], workspace_ids=frozenset({PROTHEUS}))
    uc = AddWorkspaceMember(users, access, RegisterUser(users, FakePasswordService()))

    result = await uc.execute(
        scope, email="Novo@X.com", password="senha-123", workspace_id=PROTHEUS
    )

    assert result.created and result.user.role is UserRole.USER
    assert result.user.must_change_password
    assert PROTHEUS in await access.member_workspace_ids(result.user.id)
    assert access.models[result.user.id] == {model}

    again = await uc.execute(scope, email="bia@x.com", password="ignorada", workspace_id=PROTHEUS)
    assert not again.created and PROTHEUS in await access.member_workspace_ids(people["bia"].id)

    with pytest.raises(AdminScopeDeniedError):
        await uc.execute(scope, email="adm@x.com", password="senha-123", workspace_id=PROTHEUS)
    with pytest.raises(AdminScopeDeniedError):
        await uc.execute(scope, email="z@x.com", password="senha-123", workspace_id=OUTRO)
