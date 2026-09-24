"""Testes do runtime Claude CLI: NDJSON do sandbox → eventos do TaskRunner."""

from __future__ import annotations

import asyncio
import json

import httpx

from tests.unit.agent_runtime_test_loader import ROOT, load_agent_module

_grpc_helpers = load_agent_module(
    "services.cappycloud_agent._grpc_helpers",
    ROOT / "services/cappycloud_agent/_grpc_helpers.py",
)
_session_mod = load_agent_module(
    "services.cappycloud_agent._claude_cli_session",
    ROOT / "services/cappycloud_agent/_claude_cli_session.py",
)
ClaudeCliSession = _session_mod.ClaudeCliSession


def _ndjson(*events: dict) -> bytes:
    return b"".join(json.dumps(event).encode() + b"\n" for event in events)


def _session(handler, **kwargs) -> ClaudeCliSession:
    return ClaudeCliSession(
        host="sandbox",
        session_port=8080,
        conversation_key="user:chat",
        model="anthropic/claude-sonnet-4.5",
        working_directory="/repos/sessions/abc/seller",
        internal_token="segredo",
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


async def _drain(session: ClaudeCliSession) -> list[tuple[str, object]]:
    events = []
    while True:
        event_type, data = await asyncio.wait_for(session.next_event(), timeout=2)
        events.append((event_type, data))
        if event_type in ("done", "error"):
            return events


async def test_stream_vira_eventos_e_envia_contexto_do_turno() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["token"] = request.headers.get("x-internal-token")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            content=_ndjson(
                {"type": "text", "content": "Olá"},
                {"type": "tool_start", "name": "Read", "input": "{}", "id": "t1"},
                {
                    "type": "tool_result",
                    "name": "Read",
                    "output": "ok",
                    "is_error": False,
                    "id": "t1",
                },
                {
                    "type": "done",
                    "prompt_tokens": 10,
                    "completion_tokens": 3,
                    "model_used": "claude-sonnet-5",
                },
            ),
        )

    session = _session(handler, permission_mode="request_permissions")
    await session.start("oi", attachments=[{"mime_type": "image/png", "data": b"\x89PNG"}])
    events = await _drain(session)

    assert [e[0] for e in events] == ["text", "tool_start", "tool_result", "done"]
    assert events[0][1] == {"content": "Olá"}
    assert events[3][1]["model_used"] == "claude-sonnet-5"
    assert seen["path"] == "/claude/turns"
    assert seen["token"] == "segredo"
    assert seen["body"]["conversation_key"] == "user:chat"
    assert seen["body"]["cwd"] == "/repos/sessions/abc/seller"
    assert seen["body"]["permission_mode"] == "request_permissions"
    assert seen["body"]["attachments"][0]["data_base64"] == "iVBORw=="


async def test_action_required_vira_pending_action_e_resposta_vai_para_o_turno() -> None:
    replies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/input"):
            replies.append(json.loads(request.content))
            return httpx.Response(200, json={"accepted": True})
        return httpx.Response(
            200,
            content=_ndjson(
                {
                    "type": "action_required",
                    "prompt_id": "p1",
                    "question": "Aprovar Bash?",
                    "action_type": 1,
                    "choices": ["sim", "não"],
                },
                {"type": "done", "prompt_tokens": 1, "completion_tokens": 1, "model_used": "x"},
            ),
        )

    session = _session(handler)
    await session.start("apaga o build")
    event_type, action = await asyncio.wait_for(session.next_event(), timeout=2)

    assert event_type == "action_required"
    assert isinstance(action, _grpc_helpers.PendingAction)
    assert session.pending_action == action
    assert action.choices == ["sim", "não"]

    await session.send_input("sim")
    assert session.pending_action is None
    assert replies == [{"prompt_id": "p1", "reply": "sim"}]


async def test_stream_sem_desfecho_e_erro_http_viram_evento_de_erro() -> None:
    session = _session(
        lambda request: httpx.Response(200, content=_ndjson({"type": "text", "content": "a"}))
    )
    await session.start("oi")
    events = await _drain(session)
    assert events[-1] == ("error", {"message": _grpc_helpers.GRPC_UNEXPECTED_END})

    unauthorized = _session(lambda request: httpx.Response(401, json={"error": "unauthorized"}))
    await unauthorized.start("oi")
    event_type, data = await asyncio.wait_for(unauthorized.next_event(), timeout=2)
    assert event_type == "error"
    assert "401" in data["message"]


async def test_falha_de_conexao_explica_que_o_sandbox_nao_respondeu() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("recusado", request=request)

    session = _session(handler)
    await session.start("oi")
    event_type, data = await asyncio.wait_for(session.next_event(), timeout=2)
    assert event_type == "error"
    assert "cappycloud-sandbox" in data["message"]
