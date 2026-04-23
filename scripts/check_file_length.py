#!/usr/bin/env python3
"""Pre-commit hook: rejeita arquivos com mais de MAX_LINES linhas."""

import sys

MAX_LINES = 300

failures = []
for path in sys.argv[1:]:
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            count = sum(1 for _ in f)
        if count > MAX_LINES:
            failures.append((path, count))
    except OSError:
        pass

if failures:
    for path, count in failures:
        print(f"  {path}: {count} linhas (máximo {MAX_LINES})")
    print(
        f"\n{len(failures)} arquivo(s) excedem {MAX_LINES} linhas. Refatore antes de commitar."
    )
    sys.exit(1)
