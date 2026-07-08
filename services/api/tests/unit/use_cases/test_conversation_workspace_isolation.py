from __future__ import annotations

import sys
from importlib import util
from pathlib import Path


def _load_sandbox_record_class():
    module_path = Path(__file__).resolve().parents[4] / "cappycloud_agent" / "_session_store.py"
    spec = util.spec_from_file_location("cappycloud_agent_session_store", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.SandboxRecord


SandboxRecord = _load_sandbox_record_class()


def test_sandbox_record_uses_conversation_worktree_not_user_baseline() -> None:
    record = SandboxRecord(
        user_id="user-1",
        chat_id="chat-1",
        grpc_host="sandbox",
        grpc_port=50051,
        session_root="/repos/sessions/chat-1",
        repos=[
            {
                "slug": "seller",
                "alias": "Seller",
                "worktree_path": "/repos/sessions/chat-1/Seller",
                "source_workspace_path": "/repos/users/user/default/seller/main",
            }
        ],
    )

    assert record.working_directory == "/repos/sessions/chat-1/Seller"


def test_sandbox_record_falls_back_to_session_alias_when_worktree_path_missing() -> None:
    record = SandboxRecord(
        user_id="user-1",
        chat_id="chat-1",
        grpc_host="sandbox",
        grpc_port=50051,
        session_root="/repos/sessions/chat-1",
        repos=[
            {
                "slug": "seller",
                "alias": "Seller",
                "source_workspace_path": "/repos/users/user/default/seller/main",
            }
        ],
    )

    assert record.working_directory == "/repos/sessions/chat-1/Seller"
