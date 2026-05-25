from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "tools" / "extractors" / "sql" / "src"
FIXTURES = ROOT / "services" / "api" / "tests" / "fixtures"


def _run_extractor(
    repo: Path, out_path: Path, *extra: str
) -> tuple[subprocess.CompletedProcess[str], dict]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cappy_sql_extractor.cli",
            "--repo",
            str(repo),
            "--out",
            str(out_path),
            *extra,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=35,
        check=False,
        env=env,
    )
    payload = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    return result, payload


def test_sql_extractor_emits_schema_snapshot_counts(tmp_path: Path) -> None:
    result, payload = _run_extractor(FIXTURES / "sql_basic", tmp_path / "graph.json")

    assert result.returncode == 0, result.stderr
    assert payload["source_extractor"] == "static_sql"
    assert payload["extractor_version"] == "0.1.0"
    assert payload["dialect"] == "postgres"
    assert len(payload["nodes"]) == 36
    assert len(payload["edges"]) == 43
    assert payload["diagnostics"] == []
    assert _count_by(payload["nodes"], "type") == {
        "sql_file": 5,
        "table": 3,
        "column": 10,
        "constraint": 11,
        "view": 2,
        "index": 2,
        "stored_procedure": 2,
        "trigger": 1,
    }
    assert any(
        edge["type"] == "foreign_key" and edge["confidence"] == "high" for edge in payload["edges"]
    )
    assert any(
        edge["type"] == "foreign_key"
        and edge.get("target_external") == "table:inventory.suppliers.id"
        and edge["confidence"] == "medium"
        for edge in payload["edges"]
    )
    assert any(
        edge["type"] == "indexes" and edge["attrs"]["position"] == 1 for edge in payload["edges"]
    )


def test_sql_extractor_keeps_partial_output_for_broken_file(tmp_path: Path) -> None:
    result, payload = _run_extractor(FIXTURES / "sql_broken", tmp_path / "graph.json")

    assert result.returncode == 0, result.stderr
    assert len(payload["nodes"]) == 6
    assert len(payload["edges"]) == 4
    assert len(payload["diagnostics"]) == 1
    assert any(node["name"] == "public.good_rows" for node in payload["nodes"])


def test_sql_extractor_infers_mysql_dialect(tmp_path: Path) -> None:
    result, payload = _run_extractor(FIXTURES / "sql_mysql", tmp_path / "graph.json")

    assert result.returncode == 0, result.stderr
    assert payload["dialect"] == "mysql"
    assert payload["diagnostics"] == []


def test_sql_extractor_honors_file_magic_dialect_override(tmp_path: Path) -> None:
    result, payload = _run_extractor(FIXTURES / "sql_magic", tmp_path / "graph.json")

    assert result.returncode == 0, result.stderr
    file_dialects = {
        node["name"]: node["attrs"]["dialect"]
        for node in payload["nodes"]
        if node["type"] == "sql_file"
    }
    assert file_dialects == {
        "001_postgres.sql": "postgres",
        "002_mysql_override.sql": "mysql",
    }


def test_sql_extractor_handles_empty_sql_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "000_empty.sql").write_text("", encoding="utf-8")
    (repo / "001_table.sql").write_text(
        "CREATE TABLE public.ok_rows (id SERIAL PRIMARY KEY);\n",
        encoding="utf-8",
    )

    result, payload = _run_extractor(repo, tmp_path / "graph.json")

    assert result.returncode == 0, result.stderr
    assert payload["diagnostics"] == []
    assert any(
        node["type"] == "sql_file" and node["name"] == "000_empty.sql" for node in payload["nodes"]
    )


def test_sql_extractor_performance_smoke_for_1000_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    for index in range(1000):
        (repo / f"{index:04d}.sql").write_text(
            f"CREATE TABLE public.t_{index:04d} (id SERIAL PRIMARY KEY);\n",
            encoding="utf-8",
        )

    started = time.perf_counter()
    result, payload = _run_extractor(repo, tmp_path / "graph.json")
    elapsed = time.perf_counter() - started

    assert result.returncode == 0, result.stderr
    assert elapsed < 30
    assert len(payload["nodes"]) == 4000
    assert payload["diagnostics"] == []


def _count_by(items: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item[key]] = counts.get(item[key], 0) + 1
    return counts
