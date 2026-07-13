#!/usr/bin/env python3
"""Fail fast on UTF-8 decode errors and common mojibake sequences."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


TEXT_SUFFIXES = {
    ".css",
    ".csv",
    ".html",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".mjs",
    ".py",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}

# Written with escapes on purpose: the checker itself must stay ASCII-safe.
MOJIBAKE_TOKENS = (
    "\u00c3\u0080",
    "\u00c3\u0081",
    "\u00c3\u0082",
    "\u00c3\u0083",
    "\u00c3\u0087",
    "\u00c3\u0089",
    "\u00c3\u0093",
    "\u00c3\u0095",
    "\u00c3\u00a0",
    "\u00c3\u00a1",
    "\u00c3\u00a2",
    "\u00c3\u00a3",
    "\u00c3\u00a7",
    "\u00c3\u00a9",
    "\u00c3\u00aa",
    "\u00c3\u00ad",
    "\u00c3\u00b3",
    "\u00c3\u00b4",
    "\u00c3\u00b5",
    "\u00c3\u00ba",
    "\u00c3\u0192",
    "\u00c3\u2014",
    "\u00c2\u00a0",
    "\u00c2\u00a7",
    "\u00c2\u00b7",
    "\u00e2\u20ac",
    "\u00e2\u20ac\u00a6",
    "\u00e2\u20ac\u201d",
    "\u00e2\u20ac\u201c",
    "\u00e2\u2020",
    "\u00e2\u2030",
    "\u00e2\u0153",
    "\u00e2\u201d",
    "\u00e2\u2013",
    "\u00e2\u017d",
    "\u00e2\u02c6",
    "\u00ef\u00b8",
    "\u0413\u00a0",
    "\u0413\u00a1",
    "\u0413\u00a2",
    "\u0413\u00a3",
    "\u0413\u00a7",
    "\u0413\u00a9",
    "\u0413\u00aa",
    "\u0413\u00ad",
    "\u0413\u00b3",
    "\u0413\u00b4",
    "\u0413\u00b5",
    "\u0413\u00ba",
    "\u0432\u0402",
    "\u0432\u2020",
    "\u0432\u2030",
    "\u0432\u0153",
    "\u0432\u2013",
    "\u0432\u201d",
    "\ufffd",
)

MOJIBAKE_RE = re.compile("|".join(re.escape(token) for token in MOJIBAKE_TOKENS))


def is_text_candidate(path: Path) -> bool:
    if path.suffix.lower() in TEXT_SUFFIXES:
        return True
    return path.name in {".env", ".env.example", ".gitignore"}


def line_col(text: str, index: int) -> tuple[int, int]:
    line = text.count("\n", 0, index) + 1
    line_start = text.rfind("\n", 0, index) + 1
    return line, index - line_start + 1


def check_file(path: Path) -> list[str]:
    if not path.exists() or not path.is_file() or not is_text_candidate(path):
        return []

    raw = path.read_bytes()
    if b"\0" in raw:
        return []

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return [f"{path}:{exc.start + 1}: invalid UTF-8 bytes ({exc.reason})"]

    findings: list[str] = []
    for match in MOJIBAKE_RE.finditer(text):
        line, col = line_col(text, match.start())
        snippet = text.splitlines()[line - 1].strip()
        findings.append(
            f"{path}:{line}:{col}: suspicious mojibake {match.group(0)!r}: {snippet}"
        )
        if len(findings) >= 10:
            findings.append(f"{path}: stopped after 10 findings")
            break
    return findings


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "files",
        nargs="*",
        help="Files to check; pre-commit passes changed files here.",
    )
    args = parser.parse_args(argv)

    findings: list[str] = []
    for name in args.files:
        findings.extend(check_file(Path(name)))

    if findings:
        print("Encoding check failed. Fix mojibake before committing:", file=sys.stderr)
        for finding in findings:
            print(f"  {finding}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
