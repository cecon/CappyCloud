from __future__ import annotations

import re
import tomllib
from pathlib import Path

from sqlglot import Dialect

_MAGIC_RE = re.compile(r"^\s*--\s*sqlglot:dialect\s*=\s*([A-Za-z0-9_]+)\s*$")


def resolve_repo_dialect(repo: Path, paths: list[Path], explicit: str | None) -> str:
    if explicit:
        return validate_dialect(explicit)
    config = repo / ".cappy" / "sql.toml"
    if config.exists():
        with config.open("rb") as handle:
            value = tomllib.load(handle).get("dialect")
        if isinstance(value, str) and value.strip():
            return validate_dialect(value.strip())
    return infer_dialect(paths[:5])


def file_dialect(path: Path, repo_dialect: str) -> str:
    try:
        first_line = path.read_text(encoding="utf-8", errors="ignore").splitlines()[0]
    except (OSError, IndexError):
        return repo_dialect
    match = _MAGIC_RE.match(first_line)
    return validate_dialect(match.group(1)) if match else repo_dialect


def infer_dialect(paths: list[Path]) -> str:
    sample = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")[:2000] for path in paths
    )
    upper = sample.upper()
    if "AUTO_INCREMENT" in upper or "`" in sample:
        return "mysql"
    if (
        " NVARCHAR" in upper
        or " IDENTITY" in upper
        or re.search(r"^\s*GO\s*$", upper, re.M)
    ):
        return "tsql"
    if " SERIAL" in upper or " BIGSERIAL" in upper:
        return "postgres"
    return "postgres"


def validate_dialect(dialect: str) -> str:
    cleaned = dialect.strip().lower()
    Dialect.get_or_raise(cleaned)
    return cleaned
