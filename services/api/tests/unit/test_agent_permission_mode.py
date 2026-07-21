"""Regression tests for CappyCloud agent permission-mode propagation."""

from __future__ import annotations

import sys
import types

from tests.unit.agent_runtime_test_loader import ROOT, load_agent_module


class _FakeAttachment:
    def __init__(self, **kwargs: object) -> None:
        self.__dict__.update(kwargs)


class _FakeChatRequest:
    def __init__(self, **kwargs: object) -> None:
        self.__dict__.update(kwargs)


class _FakeClientMessage:
    def __init__(self, **kwargs: object) -> None:
        self.__dict__.update(kwargs)


class _FakeUserInput:
    def __init__(self, **kwargs: object) -> None:
        self.__dict__.update(kwargs)


def _install_fake_openclaude_modules() -> None:
    pb2 = types.ModuleType("openclaude_pb2")
    pb2.Attachment = _FakeAttachment
    pb2.ChatRequest = _FakeChatRequest
    pb2.ClientMessage = _FakeClientMessage
    pb2.UserInput = _FakeUserInput
    sys.modules["openclaude_pb2"] = pb2

    pb2_grpc = types.ModuleType("openclaude_pb2_grpc")
    pb2_grpc.AgentServiceStub = object
    sys.modules["openclaude_pb2_grpc"] = pb2_grpc


_grpc_helpers = load_agent_module(
    "services.cappycloud_agent._grpc_helpers",
    ROOT / "services/cappycloud_agent/_grpc_helpers.py",
)
_grpc_event_handlers = load_agent_module(
    "services.cappycloud_agent._grpc_event_handlers",
    ROOT / "services/cappycloud_agent/_grpc_event_handlers.py",
)
_install_fake_openclaude_modules()
_grpc_session = load_agent_module(
    "services.cappycloud_agent._grpc_session",
    ROOT / "services/cappycloud_agent/_grpc_session.py",
)


def test_sanitize_permission_mode_falls_back_to_bypass_permissions() -> None:
    assert _grpc_helpers.sanitize_permission_mode("auto") == "auto"
    assert _grpc_helpers.sanitize_permission_mode("unknown") == "bypass_permissions"
    assert _grpc_helpers.sanitize_permission_mode(None) == "bypass_permissions"


def test_openclaude_startup_permission_warning_becomes_sanitized_status() -> None:
    msg = types.SimpleNamespace(
        text_chunk=types.SimpleNamespace(
            text="WARNING: permissive mode can skip the AI classifier for this provider"
        )
    )

    event_type, payload = _grpc_event_handlers.text_chunk_event(msg)

    assert event_type == "status"
    assert payload == {
        "message": "OpenClaude confirmou aviso de permissões permissivas.",
        "metadata": {
            "permission_warning": {
                "runtime_confirmed": True,
                "source": "openclaude_startup_alert",
            }
        },
    }


def test_grpc_session_chat_request_includes_sanitized_permission_mode() -> None:
    session = _grpc_session.GrpcSession(
        container_ip="127.0.0.1",
        grpc_port=50051,
        session_id="u:c",
        model="openrouter/test",
        permission_mode="bypass_permissions",
    )

    request = session._chat_request("Olá")

    assert request.permission_mode == "bypass_permissions"


def test_grpc_session_chat_request_falls_back_for_unknown_permission_mode() -> None:
    session = _grpc_session.GrpcSession(
        container_ip="127.0.0.1",
        grpc_port=50051,
        session_id="u:c",
        model="openrouter/test",
        permission_mode="unknown",
    )

    request = session._chat_request("Olá")

    assert request.permission_mode == "bypass_permissions"


def test_grpc_session_chat_request_keeps_session_ids_isolated() -> None:
    session_a = _grpc_session.GrpcSession(
        container_ip="127.0.0.1",
        grpc_port=50051,
        session_id="user:a",
        model="openrouter/test",
    )
    session_b = _grpc_session.GrpcSession(
        container_ip="127.0.0.1",
        grpc_port=50051,
        session_id="user:b",
        model="openrouter/test",
    )

    assert session_a._chat_request("A").session_id == "user:a"
    assert session_b._chat_request("B").session_id == "user:b"
