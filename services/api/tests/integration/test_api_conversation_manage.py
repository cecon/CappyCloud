"""Integration HTTP — renomear e arquivar conversas (PATCH /api/conversations/{id})."""

from __future__ import annotations

import pytest
from app.domain.entities import UserRole
from httpx import AsyncClient

from tests.conftest import InMemoryUserRepository
from tests.integration.conftest import seed_user


async def _login(client: AsyncClient, user_repo: InMemoryUserRepository, email: str) -> dict:
    await seed_user(user_repo, email, role=UserRole.USER)
    r = await client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
async def owner(client: AsyncClient, user_repo: InMemoryUserRepository) -> dict:
    return await _login(client, user_repo, "dono@test.com")


async def _create(client: AsyncClient, headers: dict, title: str) -> str:
    r = await client.post("/api/conversations", json={"title": title}, headers=headers)
    assert r.status_code == 201
    return str(r.json()["id"])


async def _titles(client: AsyncClient, headers: dict, archived: bool = False) -> list[str]:
    r = await client.get(
        "/api/conversations", params={"archived": str(archived).lower()}, headers=headers
    )
    return sorted(c["title"] for c in r.json())


async def test_renomeia_e_normaliza_espacos(client: AsyncClient, owner: dict) -> None:
    conv_id = await _create(client, owner, "Ao realizar a transmissão de um RPS…")

    r = await client.patch(
        f"/api/conversations/{conv_id}", json={"title": "  NFS-e SP   cIndOp  "}, headers=owner
    )

    assert r.status_code == 200
    assert r.json()["title"] == "NFS-e SP cIndOp"
    assert await _titles(client, owner) == ["NFS-e SP cIndOp"]


async def test_titulo_vazio_e_recusado(client: AsyncClient, owner: dict) -> None:
    conv_id = await _create(client, owner, "Teste")

    r = await client.patch(f"/api/conversations/{conv_id}", json={"title": "   "}, headers=owner)

    assert r.status_code == 400


async def test_arquivar_tira_da_lista_e_desarquivar_devolve(
    client: AsyncClient, owner: dict
) -> None:
    keep = await _create(client, owner, "Fica")
    gone = await _create(client, owner, "Arquiva")

    r = await client.patch(f"/api/conversations/{gone}", json={"archived": True}, headers=owner)
    assert r.status_code == 200 and r.json()["archived_at"]
    assert await _titles(client, owner) == ["Fica"]
    assert await _titles(client, owner, archived=True) == ["Arquiva"]
    # Continua acessível: as mensagens da conversa arquivada ainda abrem.
    assert (
        await client.get(f"/api/conversations/{gone}/messages", headers=owner)
    ).status_code == 200

    r = await client.patch(f"/api/conversations/{gone}", json={"archived": False}, headers=owner)
    assert r.json()["archived_at"] is None
    assert await _titles(client, owner) == ["Arquiva", "Fica"]
    assert keep


async def test_so_o_dono_altera(
    client: AsyncClient, owner: dict, user_repo: InMemoryUserRepository
) -> None:
    conv_id = await _create(client, owner, "Minha")
    other = await _login(client, user_repo, "outro@test.com")

    r = await client.patch(f"/api/conversations/{conv_id}", json={"title": "Hack"}, headers=other)

    assert r.status_code == 404
    assert await _titles(client, owner) == ["Minha"]
