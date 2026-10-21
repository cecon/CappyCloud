"""Admin de workspace pelas rotas HTTP reais (SQLite em memória).

Rodolfo é admin só do PROTHEUS: vê e gere o PROTHEUS e nada fora dele.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import httpx
import pytest_asyncio
from app.adapters.primary.http import (
    admin_conversations,
    admin_dashboard,
    admin_users,
    admin_workspace_access,
    admin_workspaces,
    auth,
)
from app.adapters.primary.http.deps import get_db_session
from app.adapters.primary.http.deps_auth import get_authenticated_user, get_password_service
from app.domain.entities import User, UserRole
from app.infrastructure.orm_models import Base, Conversation, Sandbox
from app.infrastructure.orm_models import User as UserORM
from app.infrastructure.orm_models_workspaces import UserWorkspaceAccess, Workspace
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.conftest import FakePasswordService

Factory = async_sessionmaker[AsyncSession]
PEOPLE = {
    "super": ("super@x.com", "admin", True),
    "adm": ("adm@x.com", "admin", False),
    "rodolfo": ("rodolfo@x.com", "user", False),
    "ana": ("ana@x.com", "user", False),
    "bia": ("bia@x.com", "user", False),
}


@pytest_asyncio.fixture
async def factory() -> AsyncGenerator[Factory]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


async def _seed(factory: Factory) -> dict[str, uuid.UUID]:
    ids = {name: uuid.uuid4() for name in [*PEOPLE, "proteus", "outro", "conv_p", "conv_o"]}
    async with factory() as session:
        sandbox = Sandbox(id=uuid.uuid4(), name="sb", host="sb", session_port=8080)
        session.add(sandbox)
        for name, (email, role, is_super) in PEOPLE.items():
            session.add(
                UserORM(
                    id=ids[name],
                    email=email,
                    hashed_password="x",
                    role=role,
                    is_super_admin=is_super,
                )
            )
        await session.flush()
        for slug in ("proteus", "outro"):
            session.add(Workspace(id=ids[slug], slug=slug, name=slug, sandbox_id=sandbox.id))
        await session.flush()
        for user, ws, admin in (
            ("rodolfo", "proteus", True),
            ("ana", "proteus", False),
            ("bia", "outro", False),
        ):
            session.add(
                UserWorkspaceAccess(
                    id=uuid.uuid4(), user_id=ids[user], workspace_id=ids[ws], is_admin=admin
                )
            )
        session.add_all(
            [
                Conversation(
                    id=ids["conv_p"], user_id=ids["ana"], title="NFS-e", workspace_id=ids["proteus"]
                ),
                Conversation(
                    id=ids["conv_o"], user_id=ids["bia"], title="Outra", workspace_id=ids["outro"]
                ),
            ]
        )
        await session.commit()
    return ids


def _client(factory: Factory, ids: dict[str, uuid.UUID], who: str) -> httpx.AsyncClient:
    app = FastAPI()
    for module in (
        admin_conversations,
        admin_dashboard,
        admin_users,
        admin_workspace_access,
        admin_workspaces,
        auth,
    ):
        app.include_router(module.router, prefix="/api")

    async def db() -> AsyncGenerator[AsyncSession]:
        async with factory() as session:
            yield session

    email, role, is_super = PEOPLE[who]
    me = User(
        id=ids[who],
        email=email,
        hashed_password="x",
        role=UserRole(role),
        is_super_admin=is_super,
    )
    app.dependency_overrides[get_db_session] = db
    app.dependency_overrides[get_authenticated_user] = lambda: me
    app.dependency_overrides[get_password_service] = lambda: FakePasswordService()
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")


async def test_me_e_conversas_ficam_no_workspace(factory: Factory) -> None:
    ids = await _seed(factory)
    async with _client(factory, ids, "rodolfo") as h:
        me = (await h.get("/api/auth/me")).json()
        listed = (await h.get("/api/admin/conversations")).json()
        own = await h.get(f"/api/admin/conversations/{ids['conv_p']}")
        foreign = await h.get(f"/api/admin/conversations/{ids['conv_o']}")
        filtered = await h.get("/api/admin/conversations", params={"workspace_id": ids["outro"]})
        dash = (await h.get("/api/admin/dashboard")).json()
        dash_other = await h.get("/api/admin/dashboard", params={"workspace_id": ids["outro"]})
    async with _client(factory, ids, "ana") as h:
        plain = await h.get("/api/admin/conversations")

    assert me["admin_workspace_ids"] == [str(ids["proteus"])]
    assert [item["title"] for item in listed["items"]] == ["NFS-e"]
    assert own.status_code == 200
    assert foreign.status_code == filtered.status_code == dash_other.status_code == 403
    assert dash["totals"]["conversations"] == 1
    assert dash["totals"]["users"] == 2
    assert plain.status_code == 403


async def test_usuarios_senha_e_novo_membro(factory: Factory) -> None:
    ids = await _seed(factory)
    async with _client(factory, ids, "rodolfo") as h:
        listed = {u["email"] for u in (await h.get("/api/admin/users")).json()}
        reset_ana = await h.post(f"/api/admin/users/{ids['ana']}/reset-password")
        reset_bia = await h.post(f"/api/admin/users/{ids['bia']}/reset-password")
        reset_adm = await h.post(f"/api/admin/users/{ids['adm']}/reset-password")
        reset_self = await h.post(f"/api/admin/users/{ids['rodolfo']}/reset-password")
        novo = await h.post(
            "/api/admin/users/workspace-member",
            json={
                "email": "novo@x.com",
                "password": "senha-123",
                "workspace_id": str(ids["proteus"]),
            },
        )
        fora = await h.post(
            "/api/admin/users/workspace-member",
            json={"email": "z@x.com", "password": "senha-123", "workspace_id": str(ids["outro"])},
        )
        role = await h.patch(f"/api/admin/users/{ids['ana']}/role", json={"role": "admin"})
    async with _client(factory, ids, "adm") as h:
        adm_reset = await h.post(f"/api/admin/users/{ids['ana']}/reset-password")

    assert listed == {"rodolfo@x.com", "ana@x.com"}
    assert reset_ana.status_code == 200 and reset_ana.json()["must_change_password"]
    assert {r.status_code for r in (reset_bia, reset_adm, reset_self, fora, role)} == {403}
    assert novo.status_code == 200 and novo.json()["role"] == "user"
    assert adm_reset.status_code == 403  # ADMIN comum segue sem redefinir senha
    async with factory() as session:
        created = await session.scalar(select(UserORM).where(UserORM.email == "novo@x.com"))
        assert created is not None and created.must_change_password
        row = await session.scalar(
            select(UserWorkspaceAccess).where(UserWorkspaceAccess.user_id == created.id)
        )
        assert row is not None and row.workspace_id == ids["proteus"] and not row.is_admin


async def test_acessos_e_flag_de_admin(factory: Factory) -> None:
    ids = await _seed(factory)
    base = "/api/admin/users/{user}/access/workspaces/{ws}"
    async with _client(factory, ids, "rodolfo") as h:
        grant = await h.post(base.format(user=ids["bia"], ws=ids["proteus"]))
        grant_other = await h.post(base.format(user=ids["ana"], ws=ids["outro"]))
        promote = await h.put(
            base.format(user=ids["ana"], ws=ids["proteus"]) + "/admin", json={"is_admin": True}
        )
        listed = (await h.get(f"/api/admin/users/{ids['bia']}/access/workspaces")).json()
    # ADMIN global comum (não super) também libera acessos e promove admin de workspace.
    async with _client(factory, ids, "adm") as h:
        promoted = await h.put(
            base.format(user=ids["ana"], ws=ids["proteus"]) + "/admin", json={"is_admin": True}
        )
        flags = (await h.get(f"/api/admin/users/{ids['ana']}/access/workspaces/admin-flags")).json()
        adm_grant = await h.post(base.format(user=ids["bia"], ws=ids["outro"]))
    async with _client(factory, ids, "rodolfo") as h:
        revoke_admin = await h.delete(base.format(user=ids["ana"], ws=ids["proteus"]))
        revoke_member = await h.delete(base.format(user=ids["bia"], ws=ids["proteus"]))

    assert grant.status_code == 204 and listed == [str(ids["proteus"])]
    assert grant_other.status_code == promote.status_code == 403
    assert promoted.status_code == 204 and flags == [str(ids["proteus"])]
    assert adm_grant.status_code == 204
    assert revoke_admin.status_code == 403
    assert revoke_member.status_code == 204


async def test_workspaces_edicao_restrita(factory: Factory) -> None:
    ids = await _seed(factory)
    async with _client(factory, ids, "rodolfo") as h:
        listed = [w["slug"] for w in (await h.get("/api/admin/workspaces")).json()]
        claude = await h.patch(
            f"/api/admin/workspaces/{ids['proteus']}",
            json={"claude_md": "# Regras", "require_ticket": True},
        )
        rename = await h.patch(f"/api/admin/workspaces/{ids['proteus']}", json={"name": "X"})
        other = await h.patch(f"/api/admin/workspaces/{ids['outro']}", json={"claude_md": "x"})
        delete = await h.delete(f"/api/admin/workspaces/{ids['proteus']}")
    async with _client(factory, ids, "adm") as h:
        adm_list = [w["slug"] for w in (await h.get("/api/admin/workspaces")).json()]
        adm_patch = await h.patch(f"/api/admin/workspaces/{ids['outro']}", json={"claude_md": "x"})

    assert listed == ["proteus"]
    assert claude.status_code == 200 and claude.json()["claude_md"] == "# Regras"
    assert {r.status_code for r in (rename, other, delete, adm_patch)} == {403}
    assert adm_list == ["outro", "proteus"]  # ADMIN comum lê a lista, mas não edita
