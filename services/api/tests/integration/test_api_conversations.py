"""Integration HTTP — /api/conversations (legacy, mantido)."""

from __future__ import annotations

import json
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


class _DiagnosticAgent(FakeAgent):
    def pipe(self, user_message, model_id, messages, body):  # type: ignore[no-untyped-def]
        del user_message, model_id, messages, body
        diagnostic = {
            "total_size_bytes": 64,
            "source": "openclaude",
            "generated_at": "2026-06-17T15:20:00Z",
            "categories": [{"key": "attachments", "size_bytes": 64}],
        }
        yield f"data: {json.dumps({'type': 'payload_diagnostic', 'diagnostics': diagnostic})}\n\n"
        yield f"data: {json.dumps({'type': 'text', 'content': 'Resposta com diagnostico'})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"


class _ActionErrorAgent(FakeAgent):
    def pipe(self, user_message, model_id, messages, body):  # type: ignore[no-untyped-def]
        del user_message, model_id, messages, body
        yield f"data: {json.dumps({'type': 'action_required', 'question': 'Continuar?'})}\n\n"
        yield f"data: {json.dumps({'type': 'error', 'message': 'Falha controlada'})}\n\n"


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
        assert r.json()["permission_mode"] == "request_permissions"

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

    async def test_stream_message_accepts_and_persists_permission_mode(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        conv_r = await client.post(
            "/api/conversations",
            json={"title": "Permission chat"},
            headers=auth_headers,
        )
        conv_id = conv_r.json()["id"]

        stream_r = await client.post(
            f"/api/conversations/{conv_id}/messages/stream",
            json={"content": "Olá agente", "permission_mode": "auto"},
            headers=auth_headers,
        )
        list_r = await client.get("/api/conversations", headers=auth_headers)

        assert stream_r.status_code == 200
        conversations = list_r.json()
        assert conversations[0]["id"] == conv_id
        assert conversations[0]["permission_mode"] == "auto"

    async def test_stream_message_rejects_unknown_permission_mode(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        conv_r = await client.post(
            "/api/conversations",
            json={"title": "Invalid permission chat"},
            headers=auth_headers,
        )
        conv_id = conv_r.json()["id"]

        r = await client.post(
            f"/api/conversations/{conv_id}/messages/stream",
            json={"content": "Olá agente", "permission_mode": "dangerously_free"},
            headers=auth_headers,
        )

        assert r.status_code == 422

    async def test_message_history_returns_assistant_payload_diagnostics(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        previous_override = app.dependency_overrides.get(get_agent)
        app.dependency_overrides[get_agent] = lambda: _DiagnosticAgent()
        try:
            conv_r = await client.post(
                "/api/conversations",
                json={"title": "Diagnostic chat"},
                headers=auth_headers,
            )
            conv_id = conv_r.json()["id"]
            stream_r = await client.post(
                f"/api/conversations/{conv_id}/messages/stream",
                json={"content": "Olá agente"},
                headers=auth_headers,
            )
            history_r = await client.get(
                f"/api/conversations/{conv_id}/messages",
                headers=auth_headers,
            )
        finally:
            if previous_override is None:
                app.dependency_overrides.pop(get_agent, None)
            else:
                app.dependency_overrides[get_agent] = previous_override

        assert stream_r.status_code == 200
        assert history_r.status_code == 200
        messages = history_r.json()
        assert messages[0]["role"] == "user"
        assert messages[0]["payload_diagnostics"] is None
        assert messages[1]["role"] == "assistant"
        assert messages[1]["payload_diagnostics"] == {
            "total_size_bytes": 64,
            "source": "openclaude",
            "generated_at": "2026-06-17T15:20:00Z",
            "categories": [
                {
                    "key": "attachments",
                    "label": "Anexos",
                    "size_bytes": 64,
                    "percentage": 100.0,
                }
            ],
        }

    async def test_action_required_and_error_events_stream(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        previous_override = app.dependency_overrides.get(get_agent)
        app.dependency_overrides[get_agent] = lambda: _ActionErrorAgent()
        try:
            conv_r = await client.post(
                "/api/conversations",
                json={"title": "Action error chat"},
                headers=auth_headers,
            )
            conv_id = conv_r.json()["id"]
            r = await client.post(
                f"/api/conversations/{conv_id}/messages/stream",
                json={"content": "Olá agente"},
                headers=auth_headers,
            )
        finally:
            if previous_override is None:
                app.dependency_overrides.pop(get_agent, None)
            else:
                app.dependency_overrides[get_agent] = previous_override

        assert r.status_code == 200
        assert b'"type": "action_required"' in r.content
        assert b'"type": "error"' in r.content
        assert b"Falha controlada" in r.content

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
