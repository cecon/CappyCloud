from __future__ import annotations

from pathlib import Path


SKIP_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "bin",
    "obj",
}


def discover_sql_files(repo: Path, scoped_paths: str | None) -> list[Path]:
    repo_root = repo.resolve()
    if scoped_paths:
        files = []
        for raw in scoped_paths.split(","):
            relative = raw.strip().replace("\\", "/").lstrip("/")
            if not relative.lower().endswith(".sql"):
                continue
            candidate = (repo_root / relative).resolve()
            if _inside(candidate, repo_root) and candidate.exists():
                files.append(candidate)
        return sorted(set(files))

    return sorted(
        path
        for path in repo_root.rglob("*.sql")
        if path.is_file()
        and _inside(path.resolve(), repo_root)
        and not _skipped(repo_root, path)
    )


def relative_path(repo: Path, path: Path) -> str:
    return path.resolve().relative_to(repo.resolve()).as_posix()


def _inside(path: Path, repo: Path) -> bool:
    try:
        path.relative_to(repo)
        return True
    except ValueError:
        return False


def _skipped(repo: Path, path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.relative_to(repo).parts)
