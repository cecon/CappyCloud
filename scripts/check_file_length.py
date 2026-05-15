#!/usr/bin/env python3
"""Pre-commit hook: rejeita arquivos de codigo com mais de MAX_LINES linhas."""

import sys
from pathlib import Path

MAX_LINES = 300
IGNORED_SUFFIXES = {".md", ".mdx", ".markdown"}
COMMENT_PREFIXES = {
    ".py": ("#",),
    ".js": ("//",),
    ".jsx": ("//",),
    ".ts": ("//",),
    ".tsx": ("//",),
}
BLOCK_COMMENT_DELIMITERS = {
    ".js": (("/*", "*/"),),
    ".jsx": (("/*", "*/"),),
    ".ts": (("/*", "*/"),),
    ".tsx": (("/*", "*/"),),
}


def is_comment_only_line(line: str, suffix: str, in_block_comment: bool) -> tuple[bool, bool]:
    stripped = line.strip()
    if not stripped:
        return True, in_block_comment

    for start, end in BLOCK_COMMENT_DELIMITERS.get(suffix, ()):
        if in_block_comment:
            return True, end not in stripped
        if stripped.startswith(start):
            return True, end not in stripped

    return stripped.startswith(COMMENT_PREFIXES.get(suffix, ())), in_block_comment


def count_code_lines(path: str) -> int:
    suffix = Path(path).suffix.lower()
    count = 0
    in_block_comment = False
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            ignored, in_block_comment = is_comment_only_line(line, suffix, in_block_comment)
            if not ignored:
                count += 1
    return count

failures = []
for path in sys.argv[1:]:
    if Path(path).suffix.lower() in IGNORED_SUFFIXES:
        continue
    try:
        count = count_code_lines(path)
        if count > MAX_LINES:
            failures.append((path, count))
    except OSError:
        pass

if failures:
    for path, count in failures:
        print(f"  {path}: {count} linhas (máximo {MAX_LINES})")
    print(
        f"\n{len(failures)} arquivo(s) de codigo excedem {MAX_LINES} linhas. "
        "Refatore antes de commitar. Arquivos Markdown sao ignorados por este gate."
    )
    sys.exit(1)
