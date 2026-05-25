from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from cappy_sql_extractor import EXTRACTOR_VERSION, SOURCE_EXTRACTOR
from cappy_sql_extractor.dialects import resolve_repo_dialect
from cappy_sql_extractor.extractor import SqlExtractor
from cappy_sql_extractor.files import discover_sql_files


def main() -> int:
    parser = argparse.ArgumentParser(prog="cappy-sql-extractor")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--paths")
    parser.add_argument("--dialect")
    args = parser.parse_args()

    started = time.perf_counter()
    repo = Path(args.repo).resolve()
    out_path = Path(args.out).resolve()
    if not repo.exists() or not repo.is_dir():
        print(f"Repo path not found: {repo}", file=sys.stderr)
        return 1

    files = discover_sql_files(repo, args.paths)
    if not files:
        print("No .sql files found.", file=sys.stderr)
        return 1

    try:
        dialect = resolve_repo_dialect(repo, files, args.dialect)
    except Exception as exc:
        print(f"Invalid SQL dialect: {exc}", file=sys.stderr)
        return 1

    extractor = SqlExtractor(repo, dialect)
    graph = extractor.extract(files)
    elapsed = int((time.perf_counter() - started) * 1000)
    payload = {
        "source_extractor": SOURCE_EXTRACTOR,
        "extractor_version": EXTRACTOR_VERSION,
        "dialect": dialect,
        "nodes": list(graph.nodes.values()),
        "edges": list(graph.edges.values()),
        "diagnostics": graph.diagnostics,
        "timings_ms": {"total": elapsed},
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    print(
        f"cappy-sql-extractor completed dialect={dialect} "
        f"files={len(files)} nodes={len(graph.nodes)} edges={len(graph.edges)} elapsed_ms={elapsed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
