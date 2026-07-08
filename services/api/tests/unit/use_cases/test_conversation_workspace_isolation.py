from __future__ import annotations

from cappycloud_agent._session_store import SandboxRecord


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
