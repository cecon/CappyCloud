"""Integration HTTP — POST /api/admin/users/{id}/reset-password (só super admin)."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

from tests.conftest import InMemoryUserRepository
from tests.integration.conftest import seed_user


async def test_volta_para_a_senha_temporaria_e_obriga_a_troca(
    client: AsyncClient, super_admin_headers: dict[str, str], user_repo: InMemoryUserRepository
) -> None:
    user = await seed_user(user_repo, "matheus@test.com")

    r = await client.post(f"/api/admin/users/{user.id}/reset-password", headers=super_admin_headers)

    assert r.status_code == 200
    assert r.json()["must_change_password"] is True
    login = await client.post(
        "/api/auth/login", data={"username": "matheus@test.com", "password": "12345678"}
    )
    assert login.status_code == 200
    # Com a troca pendente, o resto da API fica bloqueado até definir senha nova.
    token = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert (await client.get("/api/conversations", headers=token)).status_code == 403


async def test_admin_comum_nao_redefine(
    client: AsyncClient, admin_headers: dict[str, str], user_repo: InMemoryUserRepository
) -> None:
    user = await seed_user(user_repo, "alvo@test.com")

    r = await client.post(f"/api/admin/users/{user.id}/reset-password", headers=admin_headers)

    assert r.status_code == 403


async def test_nao_redefine_a_propria_senha_nem_usuario_inexistente(
    client: AsyncClient, super_admin_headers: dict[str, str], user_repo: InMemoryUserRepository
) -> None:
    me = await client.get("/api/auth/me", headers=super_admin_headers)
    own = await client.post(
        f"/api/admin/users/{me.json()['id']}/reset-password", headers=super_admin_headers
    )
    missing = await client.post(
        f"/api/admin/users/{uuid.uuid4()}/reset-password", headers=super_admin_headers
    )

    assert own.status_code == 409
    assert missing.status_code == 404


async def test_senha_temporaria_vence_em_24h(
    client: AsyncClient, super_admin_headers: dict[str, str], user_repo: InMemoryUserRepository
) -> None:
    user = await seed_user(user_repo, "atrasado@test.com")
    r = await client.post(f"/api/admin/users/{user.id}/reset-password", headers=super_admin_headers)
    expires = user_repo._store[user.id].password_reset_expires_at
    assert r.status_code == 200 and expires is not None
    assert timedelta(hours=23) < expires - datetime.now(UTC) <= timedelta(hours=24)

    # Passou o prazo sem trocar: o login com a temporária é recusado.
    user_repo._store[user.id] = replace(
        user_repo._store[user.id],
        password_reset_expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    login = await client.post(
        "/api/auth/login", data={"username": "atrasado@test.com", "password": "12345678"}
    )
    assert login.status_code == 401
    assert "expirou" in login.json()["detail"]

    # Nova redefinição volta a valer por mais 24 h.
    await client.post(f"/api/admin/users/{user.id}/reset-password", headers=super_admin_headers)
    login = await client.post(
        "/api/auth/login", data={"username": "atrasado@test.com", "password": "12345678"}
    )
    assert login.status_code == 200


async def test_trocar_a_senha_limpa_o_prazo(
    client: AsyncClient, super_admin_headers: dict[str, str], user_repo: InMemoryUserRepository
) -> None:
    user = await seed_user(user_repo, "trocou@test.com")
    await client.post(f"/api/admin/users/{user.id}/reset-password", headers=super_admin_headers)
    login = await client.post(
        "/api/auth/login", data={"username": "trocou@test.com", "password": "12345678"}
    )
    token = {"Authorization": f"Bearer {login.json()['access_token']}"}

    r = await client.post(
        "/api/auth/change-password",
        json={"current_password": "12345678", "new_password": "NovaSenha!2026"},
        headers=token,
    )

    assert r.status_code == 200 and r.json()["must_change_password"] is False
    assert user_repo._store[user.id].password_reset_expires_at is None
