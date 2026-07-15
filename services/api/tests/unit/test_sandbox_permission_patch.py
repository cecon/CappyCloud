"""Regression tests for sandbox permission patch behavior."""

from __future__ import annotations

import re

from tests.unit.agent_runtime_test_loader import ROOT

PATCH_TEXT = (ROOT / "services/sandbox/patches/multimodal-grpc-handler.patch").read_text(
    encoding="utf-8"
)


def test_request_permissions_auto_allows_read_only_tools() -> None:
    assert "+const CAPPYCLOUD_READ_ONLY_TOOLS = new Set([" in PATCH_TEXT
    assert "'Read'" in PATCH_TEXT
    assert "'Grep'" in PATCH_TEXT
    assert "'Glob'" in PATCH_TEXT
    assert (
        "+    return CAPPYCLOUD_READ_ONLY_TOOLS.has(toolName) ? { behavior: 'allow' } : null"
        in PATCH_TEXT
    )


def test_request_permissions_keeps_mutating_tools_interactive() -> None:
    assert "+const CAPPYCLOUD_MUTATING_TOOLS = new Set([" in PATCH_TEXT
    assert "'Bash'" in PATCH_TEXT
    match = re.search(
        r"\+  if \(mode === 'request_permissions'\) \{\n(?P<body>.*?)\n\+  \}",
        PATCH_TEXT,
        flags=re.DOTALL,
    )
    assert match is not None
    assert "CAPPYCLOUD_READ_ONLY_TOOLS.has(toolName)" in match.group("body")
    assert "? { behavior: 'allow' } : null" in match.group("body")
