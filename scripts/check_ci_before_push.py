#!/usr/bin/env python3
"""Run the same local gates required by GitHub Actions before pushing.

The PR workflows run API CI, Frontend CI, and pre-commit checks for every
pull_request event. This script mirrors that behavior for local pre-push hooks.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "services" / "api"
WEB_DIR = ROOT / "web"

CI_ENV = {
    "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
    "JWT_SECRET": "test-secret-ci",
    "APP_NAME": "CappyCloud Test",
}


def _is_windows() -> bool:
    return os.name == "nt"


def _api_python() -> str:
    candidate = API_DIR / ".venv" / ("Scripts/python.exe" if _is_windows() else "bin/python")
    return str(candidate) if candidate.exists() else sys.executable


def _run(
    label: str,
    command: list[str],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
    dry_run: bool = False,
) -> None:
    print(f"\n==> {label}")
    print(f"$ {' '.join(command)}")
    if dry_run:
        return

    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    try:
        subprocess.run(command, cwd=cwd, env=merged_env, check=True)
    except FileNotFoundError as exc:
        raise SystemExit(f"Command not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc


def _run_with_fallback(
    label: str,
    command: list[str],
    fallback: list[str],
    *,
    cwd: Path = ROOT,
    dry_run: bool = False,
) -> None:
    print(f"\n==> {label}")
    print(f"$ {' '.join(command)} || {' '.join(fallback)}")
    if dry_run:
        return

    primary = subprocess.run(command, cwd=cwd, env=os.environ.copy(), check=False)
    if primary.returncode == 0:
        return
    subprocess.run(fallback, cwd=cwd, env=os.environ.copy(), check=True)


def _frontend_package_manager() -> tuple[str, str]:
    preferred = (
        ("pnpm", "pnpm.cmd") if (WEB_DIR / "pnpm-lock.yaml").exists() else ("npm", "npm.cmd")
    )
    fallbacks = tuple(
        item for item in ("pnpm", "pnpm.cmd", "npm", "npm.cmd") if item not in preferred
    )
    for executable in preferred + fallbacks:
        resolved = shutil.which(executable)
        if resolved:
            name = "pnpm" if "pnpm" in executable else "npm"
            return resolved, name
    raise SystemExit("Neither npm nor pnpm was found on PATH.")


def run_pre_commit(base_ref: str, dry_run: bool) -> None:
    _run(
        "Pre-commit checks",
        [_api_python(), "-m", "pre_commit", "run", "--from-ref", base_ref, "--to-ref", "HEAD"],
        dry_run=dry_run,
    )


def run_api_ci(dry_run: bool) -> None:
    py = _api_python()
    for label, command in (
        ("API ruff", [py, "-m", "ruff", "check", "."]),
        ("API ruff format", [py, "-m", "ruff", "format", "--check", "."]),
        ("API mypy", [py, "-m", "mypy", "app/"]),
        ("API pytest", [py, "-m", "pytest"]),
    ):
        _run(label, command, cwd=API_DIR, env=CI_ENV, dry_run=dry_run)


def run_frontend_ci(dry_run: bool) -> None:
    manager, name = _frontend_package_manager()
    if name == "pnpm":
        _run(
            "Frontend dependencies",
            [manager, "install", "--frozen-lockfile"],
            cwd=WEB_DIR,
            dry_run=dry_run,
        )
    else:
        _run_with_fallback(
            "Frontend dependencies",
            [manager, "ci", "--prefer-offline"],
            [manager, "install"],
            cwd=WEB_DIR,
            dry_run=dry_run,
        )
    _run("Frontend ESLint", [manager, "run", "lint"], cwd=WEB_DIR, dry_run=dry_run)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local CI gates before pushing a PR branch.")
    parser.add_argument(
        "--base-ref",
        default=os.environ.get("CAPPYCLOUD_CI_BASE_REF", "origin/main"),
        help="Base ref for pre-commit changed-file checks. Default: origin/main.",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print commands without running them."
    )
    parser.add_argument("--skip-pre-commit", action="store_true", help="Skip pre-commit gate.")
    parser.add_argument("--skip-api", action="store_true", help="Skip API CI gate.")
    parser.add_argument("--skip-frontend", action="store_true", help="Skip frontend CI gate.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if os.environ.get("CAPPYCLOUD_SKIP_CI_HOOK") == "1":
        print("CAPPYCLOUD_SKIP_CI_HOOK=1 set; skipping local CI hook.")
        return 0

    if not args.skip_pre_commit:
        run_pre_commit(args.base_ref, args.dry_run)
    if not args.skip_api:
        run_api_ci(args.dry_run)
    if not args.skip_frontend:
        run_frontend_ci(args.dry_run)

    print("\nLocal CI gates passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
