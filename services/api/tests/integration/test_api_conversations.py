"""Integration HTTP — /api/conversations (legacy, mantido)."""

from __future__ import annotations

import threading
import uuid

import pytest
from app.adapters.primary.http.deps import get_agent, get_db_session
from app.domain.entities import UserRole
from app.main import app
from httpx import AsyncClient

from tests.conftest import FakeAgent, InMemoryUserRepository
from tests.integration.conftest import seed_user


class _ThreadRecordingCancelAgent(FakeAgent):
    def __init__(self) -> None:
        super().__init__()
        self.cancel_thread_id: int | None = None
        self.cancelled_conversation_id: str | None = None

    def cancel_conversation(self, conversation_id: str) -> bool:
        self.cancel_thread_id = threading.get_ident()
        self.cancelled_conversation_id = conversation_id
        return True


class _CancelResult:
    def fetchone(self) -> object:
        return object()


class _CancelDbSession:
    async def execute(self, *_args: object, **_kwargs: object) -> _CancelResult:
        return _CancelResult()


class TestConversationEndpoints:
    @pytest.fixture
    async def auth_headers(
        self, client: AsyncClient, user_repo: InMemoryUserRepository
    ) -> dict[str, str]:
        """USER comum (PR1 ainda não filtra conversas por permissão)."""
        await seed_user(user_repo, "conv@test.com", role=UserRole.USER)
        r = await client.post(
            "/api/auth/login",
            data={"username": "conv@test.com", "password": "password123"},
        )
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    async def test_list_conversations_empty(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.get("/api/conversations", headers=auth_headers)
        assert r.status_code == 200
        assert r.json() == []

    async def test_create_conversation(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await client.post(
            "/api/conversations",
            json={"title": "Meu chat"},
            headers=auth_headers,
        )
        assert r.status_code == 201
        assert r.json()["title"] == "Meu chat"

    async def test_list_messages_not_found(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        fake_id = "00000000-0000-0000-0000-000000000000"
        r = await client.get(f"/api/conversations/{fake_id}/messages", headers=auth_headers)
        assert r.status_code == 404

    async def test_stream_message(self, client: AsyncClient, auth_headers: dict[str, str]) -> None:
        conv_r = await client.post(
            "/api/conversations",
            json={"title": "Stream chat"},
            headers=auth_headers,
        )
        conv_id = conv_r.json()["id"]
        r = await client.post(
            f"/api/conversations/{conv_id}/messages/stream",
            json={"content": "Olá agente"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]
        assert len(r.content) > 0

    async def test_cancel_conversation_uses_worker_thread(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        agent = _ThreadRecordingCancelAgent()
        loop_thread_id = threading.get_ident()
        conv_id = str(uuid.uuid4())
        previous_override = app.dependency_overrides.get(get_agent)
        previous_db_override = app.dependency_overrides.get(get_db_session)
        app.dependency_overrides[get_agent] = lambda: agent
        app.dependency_overrides[get_db_session] = lambda: _CancelDbSession()
        try:
            r = await client.post(
                f"/api/conversations/{conv_id}/cancel",
                headers=auth_headers,
            )
        finally:
            if previous_override is None:
                app.dependency_overrides.pop(get_agent, None)
            else:
                app.dependency_overrides[get_agent] = previous_override
            if previous_db_override is None:
                app.dependency_overrides.pop(get_db_session, None)
            else:
                app.dependency_overrides[get_db_session] = previous_db_override

        assert r.status_code == 200
        assert r.json() == {"cancelled": True}
        assert agent.cancelled_conversation_id == conv_id
        assert agent.cancel_thread_id is not None
        assert agent.cancel_thread_id != loop_thread_id
