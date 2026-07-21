"""Integration HTTP tests for chat slash commands."""

from __future__ import annotations

from httpx import AsyncClient


async def test_conversation_commands_catalog_and_ctx_execution(
    client: AsyncClient,
    user_headers: dict[str, str],
) -> None:
    created = await client.post(
        "/api/conversations",
        json={"title": "Commands chat"},
        headers=user_headers,
    )
    conversation_id = created.json()["id"]

    catalog = await client.get(
        f"/api/conversations/{conversation_id}/commands",
        headers=user_headers,
    )
    executed = await client.post(
        f"/api/conversations/{conversation_id}/commands/execute",
        json={
            "command": "/ctx",
            "arguments": {},
            "confirmed": False,
            "client_request_id": "req-ctx",
        },
        headers=user_headers,
    )

    assert catalog.status_code == 200
    assert catalog.json()["commands"][0]["name"] == "/ctx"
    assert executed.status_code == 200
    assert executed.json()["status"] == "completed"
    assert "Contexto usado" in executed.json()["message"]
