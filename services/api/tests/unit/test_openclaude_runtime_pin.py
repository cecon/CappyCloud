"""Regression tests for the OpenClaude runtime pin."""

from __future__ import annotations

import re

from tests.unit.agent_runtime_test_loader import ROOT

DOCKERFILE = (ROOT / "services/sandbox/Dockerfile").read_text(encoding="utf-8")
UPGRADE_RESEARCH = (ROOT / "specs/008-openclaude-current-upgrade/research.md").read_text(
    encoding="utf-8"
)

TARGET_COMMIT = "6e30b40de00868a968bdcaa0c3d0dd915d69d357"


def test_sandbox_dockerfile_pins_openclaude_v028_commit() -> None:
    match = re.search(r"^ARG OPENCLAUDE_REF=([0-9a-f]{40})$", DOCKERFILE, re.MULTILINE)

    assert match is not None
    assert match.group(1) == TARGET_COMMIT


def test_upgrade_research_records_target_commit() -> None:
    assert TARGET_COMMIT in UPGRADE_RESEARCH
    assert "0.28.0" in UPGRADE_RESEARCH
