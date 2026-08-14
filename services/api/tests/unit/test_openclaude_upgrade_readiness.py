"""Readiness checks for the OpenClaude 0.28.0 upgrade artifacts."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SPEC_DIR = ROOT / "specs" / "008-openclaude-current-upgrade"
TARGET_VERSION = "0.28.0"
TARGET_COMMIT = "6e30b40de00868a968bdcaa0c3d0dd915d69d357"
BASELINE_VERSION = "0.24.0"


def test_release_impact_matrix_covers_required_release_themes() -> None:
    matrix = (SPEC_DIR / "release-impact-matrix.md").read_text(encoding="utf-8")

    for theme in (
        "0.25.0 live context/token visibility",
        "0.25.0 provider onboarding",
        "0.26.0 long-running tool behavior",
        "0.27.0 auth-ready loopback proxy hosts",
        "0.27.0 new Ling/Macaron catalog entries",
        "0.27.0 refreshed OpenClaude web identity",
        "0.27.0 subagents from multi-repository parent sessions",
        "0.27.0 tool-failure guard",
        "0.28.0 model-picker catalog rebuild performance",
        "0.28.0 monotonic query watchdog deadlines",
        "0.28.0 Node module compile cache",
        "OpenClaude buddy companions and terminal-only commands",
    ):
        assert theme in matrix

    for decision in ("Adapt UI", "Validate existing", "Runtime-only", "Out of scope"):
        assert decision in matrix


def test_target_version_and_baseline_are_consistent_across_artifacts() -> None:
    files = [
        ROOT / "services" / "sandbox" / "Dockerfile",
        SPEC_DIR / "research.md",
        SPEC_DIR / "patch-audit.md",
        SPEC_DIR / "release-impact-matrix.md",
        ROOT / "docs" / "how-to" / "agent-runtime-context.md",
    ]
    contents = "\n".join(path.read_text(encoding="utf-8") for path in files)

    assert TARGET_VERSION in contents
    assert TARGET_COMMIT in contents
    assert BASELINE_VERSION in contents
    current_runtime_docs = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT / "services" / "sandbox" / "Dockerfile",
            ROOT / "docs" / "how-to" / "agent-runtime-context.md",
        )
    )
    assert "1b7e55058cca57f2f83d7e229441631794286c1a" not in current_runtime_docs
