"""Regression tests for the OpenClaude v0.24 patch audit artifact."""

from __future__ import annotations

from tests.unit.agent_runtime_test_loader import ROOT

RUNTIME_AUDIT = (ROOT / "specs/008-openclaude-v024-chat-commands/runtime-audit.md").read_text(
    encoding="utf-8"
)


def test_patch_audit_records_retained_and_rebased_patches() -> None:
    expected_decisions = {
        "`grep-tool-n-alias.patch`": "retained",
        "`multimodal-proto.patch`": "retained",
        "`read-empty-pages.patch`": "retained",
        "`multimodal-grpc-handler.patch`": "rebase required",
        "`worktree-tool-guard.patch`": "rebase required",
        "`mcp-grpc-integration.patch`": "rebase required",
        "numeric grep patches": "rebase required",
    }

    for patch_name, decision in expected_decisions.items():
        assert patch_name in RUNTIME_AUDIT
        assert decision in RUNTIME_AUDIT


def test_patch_audit_documents_tolerated_rejects_before_rollout() -> None:
    assert "7 rejects" in RUNTIME_AUDIT
    assert "before production rollout" in RUNTIME_AUDIT
