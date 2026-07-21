"""Regression tests for the OpenClaude runtime pin."""

from __future__ import annotations

import re

from tests.unit.agent_runtime_test_loader import ROOT

DOCKERFILE = (ROOT / "services/sandbox/Dockerfile").read_text(encoding="utf-8")
RUNTIME_AUDIT = (ROOT / "specs/008-openclaude-v024-chat-commands/runtime-audit.md").read_text(
    encoding="utf-8"
)

TARGET_COMMIT = "2ff93a10bf88ab6d7030fc4ade5316a7424fa2f9"


def test_sandbox_dockerfile_pins_openclaude_v024_commit() -> None:
    match = re.search(r"^ARG OPENCLAUDE_REF=([0-9a-f]{40})$", DOCKERFILE, re.MULTILINE)

    assert match is not None
    assert match.group(1) == TARGET_COMMIT


def test_runtime_audit_records_target_commit_and_local_build() -> None:
    assert TARGET_COMMIT in RUNTIME_AUDIT
    assert "cappycloud-sandbox:openclaude-v024-check" in RUNTIME_AUDIT
    assert 'openclaude":"running"' in RUNTIME_AUDIT
