from __future__ import annotations

from sqlglot import exp


def safe(value: str) -> str:
    return " ".join(str(value or "").strip().split()).replace("#", "%23") or "unknown"


def sandbox_id(path: str, kind: str, name: str) -> str:
    return f"sql:{path}#{kind}:{safe(name)}"


def table_name(table: exp.Expression, dialect: str) -> str:
    if isinstance(table, exp.Schema):
        table = table.this
    if not isinstance(table, exp.Table):
        return normalize_identifier(str(table), dialect)

    name = normalize_identifier(_identifier_text(table.this), dialect)
    schema_expr = table.args.get("db")
    schema = (
        normalize_identifier(_identifier_text(schema_expr), dialect)
        if schema_expr
        else ""
    )
    return f"{schema}.{name}" if schema else name


def column_name(node: exp.Expression, dialect: str) -> str:
    if isinstance(node, exp.Column):
        return normalize_identifier(_identifier_text(node.this), dialect)
    if isinstance(node, exp.Identifier):
        return normalize_identifier(_identifier_text(node), dialect)
    return normalize_identifier(str(node), dialect)


def normalize_identifier(value: str, dialect: str, *, quoted: bool = False) -> str:
    cleaned = value.strip().strip('[]`"')
    if quoted or dialect in {"tsql"}:
        return cleaned
    return cleaned.lower()


def schema_part(qualified: str) -> str:
    parts = qualified.split(".")
    return ".".join(parts[:-1]) if len(parts) > 1 else ""


def _identifier_text(node: object) -> str:
    if isinstance(node, exp.Identifier):
        return str(node.this)
    if hasattr(node, "name"):
        return str(node.name)
    return str(node or "")
