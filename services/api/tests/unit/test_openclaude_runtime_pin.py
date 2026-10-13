"""Regression tests for the OpenClaude runtime pin."""

from __future__ import annotations

import re

from tests.unit.agent_runtime_test_loader import ROOT

DOCKERFILE = (ROOT / "services/sandbox/Dockerfile").read_text(encoding="utf-8")
RUNTIME_DOC = (ROOT / "docs/how-to/agent-runtime-context.md").read_text(encoding="utf-8")

TARGET_VERSION = "0.32.0"
TARGET_COMMIT = "88baafe316d610f8f7eadcc186ecd044e718a1b9"


def test_sandbox_dockerfile_pins_openclaude_v032_commit() -> None:
    match = re.search(r"^ARG OPENCLAUDE_REF=([0-9a-f]{40})$", DOCKERFILE, re.MULTILINE)

    assert match is not None
    assert match.group(1) == TARGET_COMMIT


def test_sandbox_clones_openclaude_from_its_current_home() -> None:
    assert "https://github.com/Twigpine/openclaude.git" in DOCKERFILE
    assert "github.com/Gitlawb/openclaude" not in DOCKERFILE


def test_runtime_doc_records_target_commit() -> None:
    assert TARGET_COMMIT in RUNTIME_DOC
    assert f"## OpenClaude {TARGET_VERSION}" in RUNTIME_DOC
