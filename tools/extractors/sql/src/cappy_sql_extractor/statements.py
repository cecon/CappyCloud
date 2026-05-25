from __future__ import annotations

import re

from cappy_sql_extractor.models import StatementText

_DOLLAR_TAG_RE = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$")


def split_sql_statements(source: str) -> list[StatementText]:
    statements: list[StatementText] = []
    start = 0
    line = 1
    start_line = 1
    index = 0
    quote: str | None = None
    dollar_tag: str | None = None
    line_comment = False
    block_comment = False

    while index < len(source):
        char = source[index]
        nxt = source[index + 1] if index + 1 < len(source) else ""

        if char == "\n":
            line += 1
            line_comment = False

        if line_comment:
            index += 1
            continue
        if block_comment:
            if char == "*" and nxt == "/":
                block_comment = False
                index += 2
                continue
            index += 1
            continue
        if dollar_tag:
            if source.startswith(dollar_tag, index):
                index += len(dollar_tag)
                dollar_tag = None
                continue
            index += 1
            continue
        if quote:
            if char == quote:
                if nxt == quote:
                    index += 2
                    continue
                quote = None
            index += 1
            continue

        if char == "-" and nxt == "-":
            line_comment = True
            index += 2
            continue
        if char == "/" and nxt == "*":
            block_comment = True
            index += 2
            continue
        if char in {"'", '"', "`"}:
            quote = char
            index += 1
            continue
        match = _DOLLAR_TAG_RE.match(source, index)
        if match:
            dollar_tag = match.group(0)
            index += len(dollar_tag)
            continue
        if char == ";":
            _append_statement(statements, source[start : index + 1], start_line, line)
            start = index + 1
            start_line = line
        index += 1

    _append_statement(statements, source[start:], start_line, line)
    return statements


def _append_statement(
    statements: list[StatementText],
    sql: str,
    line_start: int,
    line_end: int,
) -> None:
    stripped = sql.strip()
    if stripped:
        leading_lines = len(sql) - len(sql.lstrip("\r\n"))
        statements.append(
            StatementText(
                sql=stripped,
                line_start=line_start + leading_lines,
                line_end=line_end,
            )
        )
