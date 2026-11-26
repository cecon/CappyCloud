"""ADMIN global que não é super admin edita os workspaces de que é admin.

Caso real: o Alef é ADMIN global e admin do PROTHEUS-azure. Antes, a edição do
workspace pedia super admin a todo ADMIN global e devolvia 403 sem olhar o
``is_admin`` do acesso dele.
"""

from __future__ import annotations

import uuid

from app.infrastructure.orm_models_workspaces import UserWorkspaceAccess

from tests.adapter.test_workspace_admins import Factory, _client, _seed, factory  # noqa: F401


async def _make_adm_admin_of_proteus(factory: Factory, ids: dict[str, uuid.UUID]) -> None:  # noqa: F811
    async with factory() as session:
        session.add(
            UserWorkspaceAccess(
                id=uuid.uuid4(), user_id=ids["adm"], workspace_id=ids["proteus"], is_admin=True
            )
        )
        await session.commit()


async def test_admin_global_edita_o_workspace_que_administra(factory: Factory) -> None:  # noqa: F811
    ids = await _seed(factory)
    await _make_adm_admin_of_proteus(factory, ids)
    async with _client(factory, ids, "adm") as h:
        me = (await h.get("/api/auth/me")).json()
        own = await h.patch(
            f"/api/admin/workspaces/{ids['proteus']}",
            json={"claude_md": "# Regras", "prompt_template": "Chamado:"},
        )
        other = await h.patch(f"/api/admin/workspaces/{ids['outro']}", json={"claude_md": "x"})
        rename = await h.patch(f"/api/admin/workspaces/{ids['proteus']}", json={"name": "X"})
        listed = [w["slug"] for w in (await h.get("/api/admin/workspaces")).json()]

    assert me["admin_workspace_ids"] == [str(ids["proteus"])]
    assert own.status_code == 200
    assert own.json()["prompt_template"] == "Chamado:"
    assert other.status_code == 403
    assert rename.status_code == 403  # nome e repositórios continuam com o super admin
    assert listed == ["outro", "proteus"]  # a leitura continua vendo todos


async def test_admin_global_sem_workspace_continua_sem_editar(factory: Factory) -> None:  # noqa: F811
    ids = await _seed(factory)
    async with _client(factory, ids, "adm") as h:
        me = (await h.get("/api/auth/me")).json()
        edit = await h.patch(f"/api/admin/workspaces/{ids['proteus']}", json={"claude_md": "x"})
    async with _client(factory, ids, "super") as h:
        super_me = (await h.get("/api/auth/me")).json()

    assert me["admin_workspace_ids"] == []
    assert edit.status_code == 403
    assert super_me["admin_workspace_ids"] == []
