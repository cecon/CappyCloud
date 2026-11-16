"""Times do workspace pelas rotas HTTP reais (SQLite em memória).

Rodolfo é admin do PROTHEUS (``proteus``): cria os times dele e põe as pessoas
nos times. Fora do PROTHEUS, nada.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import httpx
from app.adapters.primary.http import admin_workspace_access, admin_workspace_teams
from app.adapters.primary.http.deps import get_db_session
from app.adapters.primary.http.deps_auth import get_authenticated_user
from app.domain.entities import User, UserRole
from app.infrastructure.orm_models_workspaces import UserWorkspaceAccess
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.adapter.test_workspace_admins import PEOPLE, Factory, _seed, factory  # noqa: F401


def _client(factory: Factory, ids: dict[str, uuid.UUID], who: str) -> httpx.AsyncClient:  # noqa: F811
    app = FastAPI()
    for module in (admin_workspace_access, admin_workspace_teams):
        app.include_router(module.router, prefix="/api")

    async def db() -> AsyncGenerator[AsyncSession]:
        async with factory() as session:
            yield session

    email, role, is_super = PEOPLE[who]
    me = User(
        id=ids[who], email=email, hashed_password="x", role=UserRole(role), is_super_admin=is_super
    )
    app.dependency_overrides[get_db_session] = db
    app.dependency_overrides[get_authenticated_user] = lambda: me
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")


def _teams_url(ids: dict[str, uuid.UUID], ws: str = "proteus") -> str:
    return f"/api/admin/workspaces/{ids[ws]}/teams"


def _team_url(ids: dict[str, uuid.UUID], user: str, ws: str = "proteus") -> str:
    return f"/api/admin/users/{ids[user]}/access/workspaces/{ids[ws]}/team"


async def test_admin_do_workspace_cria_renomeia_e_apaga_times(factory: Factory) -> None:  # noqa: F811
    ids = await _seed(factory)
    async with _client(factory, ids, "rodolfo") as h:
        sped = await h.post(_teams_url(ids), json={"name": "  PROTHEUS   SPED "})
        dup = await h.post(_teams_url(ids), json={"name": "protheus sped"})
        blank = await h.post(_teams_url(ids), json={"name": "   "})
        prime = (await h.post(_teams_url(ids), json={"name": "PROTHEUS PRIME SP"})).json()
        renamed = await h.patch(f"{_teams_url(ids)}/{prime['id']}", json={"name": "Prime SP"})
        clash = await h.patch(f"{_teams_url(ids)}/{prime['id']}", json={"name": "Protheus Sped"})
        foreign = await h.post(_teams_url(ids, "outro"), json={"name": "X"})
        listed = (await h.get(_teams_url(ids))).json()

    assert sped.status_code == 201
    assert sped.json()["name"] == "PROTHEUS SPED"
    assert dup.status_code == 409
    assert blank.status_code == 422
    assert renamed.json()["name"] == "Prime SP"
    assert clash.status_code == 409
    assert foreign.status_code == 403
    assert [(t["name"], t["members"]) for t in listed] == [("Prime SP", 0), ("PROTHEUS SPED", 0)]


async def test_time_da_pessoa_e_limpeza_ao_apagar(factory: Factory) -> None:  # noqa: F811
    ids = await _seed(factory)
    async with _client(factory, ids, "super") as h:
        other_team = (await h.post(_teams_url(ids, "outro"), json={"name": "Outro"})).json()
    async with _client(factory, ids, "rodolfo") as h:
        team = (await h.post(_teams_url(ids), json={"name": "SPED"})).json()
        ok = await h.put(_team_url(ids, "ana"), json={"team_id": team["id"]})
        wrong_ws = await h.put(_team_url(ids, "ana"), json={"team_id": other_team["id"]})
        # bia não tinha acesso ao PROTHEUS: ganhar time concede o acesso.
        granted = await h.put(_team_url(ids, "bia"), json={"team_id": team["id"]})
        global_admin = await h.put(_team_url(ids, "adm"), json={"team_id": team["id"]})
        outside = await h.put(_team_url(ids, "bia", "outro"), json={"team_id": None})
        ana_teams = (await h.get(f"/api/admin/users/{ids['ana']}/access/workspaces/teams")).json()
        listed = (await h.get(_teams_url(ids))).json()
        deleted = await h.delete(f"{_teams_url(ids)}/{team['id']}")
        after = (await h.get(f"/api/admin/users/{ids['ana']}/access/workspaces/teams")).json()

    assert ok.status_code == 204
    assert wrong_ws.status_code == 422
    assert granted.status_code == 204
    assert global_admin.status_code == 403
    assert outside.status_code == 403
    assert ana_teams == {str(ids["proteus"]): team["id"]}
    assert listed[0]["members"] == 2
    assert deleted.status_code == 204
    assert after == {}
    async with factory() as session:
        rows = (
            await session.execute(
                select(UserWorkspaceAccess.user_id).where(
                    UserWorkspaceAccess.workspace_id == ids["proteus"]
                )
            )
        ).scalars()
        assert ids["bia"] in set(rows)
