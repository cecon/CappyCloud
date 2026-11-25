"""Prompt modelo do workspace: o admin do workspace cadastra, o chat recebe."""

from __future__ import annotations

from app.adapters.primary.http import workspaces_accessible

from tests.adapter.test_workspace_admins import Factory, _client, _seed, factory  # noqa: F401


async def test_admin_do_workspace_cadastra_e_o_chat_recebe(factory: Factory) -> None:  # noqa: F811
    ids = await _seed(factory)
    modelo = "Chamado:\nMunicípio:\nO que aconteceu:"
    async with _client(factory, ids, "rodolfo") as h:
        saved = await h.patch(
            f"/api/admin/workspaces/{ids['proteus']}", json={"prompt_template": modelo}
        )
        other = await h.patch(
            f"/api/admin/workspaces/{ids['outro']}", json={"prompt_template": "x"}
        )
        h._transport.app.include_router(workspaces_accessible.router, prefix="/api")  # type: ignore[attr-defined]
        accessible = (await h.get("/api/workspaces/accessible")).json()

    assert saved.status_code == 200 and saved.json()["prompt_template"] == modelo
    assert other.status_code == 403
    assert [(w["slug"], w["prompt_template"]) for w in accessible] == [("proteus", modelo)]


async def test_workspace_sem_prompt_modelo_vem_vazio(factory: Factory) -> None:  # noqa: F811
    ids = await _seed(factory)
    async with _client(factory, ids, "super") as h:
        got = await h.get(f"/api/admin/workspaces/{ids['outro']}")
        too_long = await h.patch(
            f"/api/admin/workspaces/{ids['outro']}", json={"prompt_template": "x" * 8001}
        )

    assert got.status_code == 200 and got.json()["prompt_template"] == ""
    assert too_long.status_code == 422
