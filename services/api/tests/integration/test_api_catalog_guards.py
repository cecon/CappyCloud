"""Integration HTTP — só super admin altera repositórios, git providers e workspaces.

Antes, estas rotas exigiam apenas login: qualquer utilizador criava ou apagava
repositórios e credenciais Git.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

_REPO_ID = uuid.uuid4()
_PROVIDER_ID = uuid.uuid4()

_MUTATIONS = [
    ("post", "/api/repositories", {"slug": "x", "name": "x", "clone_url": "https://x"}),
    ("patch", f"/api/repositories/{_REPO_ID}", {"name": "y"}),
    ("post", f"/api/repositories/{_REPO_ID}/sync", None),
    ("delete", f"/api/repositories/{_REPO_ID}", None),
    ("get", "/api/git-providers", None),
    ("post", "/api/git-providers", {"name": "p", "provider_type": "github", "token": "t"}),
    ("patch", f"/api/git-providers/{_PROVIDER_ID}/token", {"token": "t"}),
    ("delete", f"/api/git-providers/{_PROVIDER_ID}", None),
    ("get", "/api/admin/workspaces", None),
    ("post", "/api/admin/workspaces", {"slug": "loja", "name": "Loja", "sandbox_id": str(_REPO_ID)}),
    ("patch", f"/api/admin/workspaces/{_REPO_ID}", {"name": "x"}),
    ("delete", f"/api/admin/workspaces/{_REPO_ID}", None),
    ("post", f"/api/admin/users/{_REPO_ID}/access/workspaces/{_REPO_ID}", None),
]


@pytest.mark.parametrize(("method", "url", "body"), _MUTATIONS)
async def test_admin_sem_super_admin_recebe_403(
    client: AsyncClient,
    admin_headers: dict[str, str],
    method: str,
    url: str,
    body: dict | None,
) -> None:
    kwargs = {"headers": admin_headers}
    if body is not None:
        kwargs["json"] = body
    r = await getattr(client, method)(url, **kwargs)
    assert r.status_code == 403
    assert "super admin" in r.json()["detail"]


@pytest.mark.parametrize(("method", "url", "body"), _MUTATIONS)
async def test_usuario_comum_recebe_403(
    client: AsyncClient,
    user_headers: dict[str, str],
    method: str,
    url: str,
    body: dict | None,
) -> None:
    kwargs = {"headers": user_headers}
    if body is not None:
        kwargs["json"] = body
    r = await getattr(client, method)(url, **kwargs)
    assert r.status_code == 403


async def test_status_de_sandbox_exige_admin(
    client: AsyncClient, user_headers: dict[str, str]
) -> None:
    r = await client.patch(
        f"/api/sandboxes/{uuid.uuid4()}/status",
        params={"status": "offline"},
        headers=user_headers,
    )
    assert r.status_code == 403
