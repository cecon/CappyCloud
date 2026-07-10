"""Document-scoped schema graph extraction and materialization."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.orm_models import Document
from app.infrastructure.orm_models_document_graph import DocumentGraphEdge, DocumentGraphNode

_TABLE_HEADING_RE = re.compile(
    r"^####\s+((?:[A-Za-z_][\w-]*\.)?[A-Za-z_][\w-]*)\b",
    re.MULTILINE,
)
_PK_RE = re.compile(r"^\s*-\s*PK:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
_COLUMN_RE = re.compile(r"^\s*-\s+`([^`]+)`\s*(.*)$", re.MULTILINE)
_FK_RE = re.compile(r"\bFK\s*->\s*([A-Za-z_][\w-]*(?:\.[A-Za-z_][\w-]*){1,2})")


@dataclass(frozen=True)
class ParsedColumn:
    name: str
    raw_type: str
    is_pk: bool
    target_table: str | None = None
    target_column: str | None = None


@dataclass(frozen=True)
class ParsedTable:
    name: str
    pk: list[str]
    columns: list[ParsedColumn] = field(default_factory=list)


@dataclass(frozen=True)
class ParsedDocumentGraph:
    tables: list[ParsedTable]


def parse_document_graph(text: str) -> ParsedDocumentGraph:
    """Extract a lightweight table graph from imported schema markdown."""
    tables: list[ParsedTable] = []
    matches = list(_TABLE_HEADING_RE.finditer(text or ""))
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section = text[start:end]
        table_name = _normalise_table_name(match.group(1))
        pk = _parse_pk(section)
        columns = _parse_columns(section, table_name, pk)
        if columns or pk:
            tables.append(ParsedTable(name=table_name, pk=pk, columns=columns))
    return ParsedDocumentGraph(tables=tables)


async def replace_document_graph(
    session: AsyncSession,
    document: Document,
    raw_text: str,
) -> None:
    """Replace all graph rows for a document with rows extracted from ``raw_text``."""
    await delete_document_graph(session, document.id)
    graph = parse_document_graph(raw_text)
    if not graph.tables:
        return

    nodes: dict[str, DocumentGraphNode] = {}
    edges: list[DocumentGraphEdge] = []
    for table in graph.tables:
        table_key = _table_key(table.name)
        table_node = DocumentGraphNode(
            id=uuid.uuid4(),
            document_id=document.id,
            repository_id=document.repository_id,
            node_key=table_key,
            kind="table",
            name=table.name,
            attrs={"pk": table.pk, "columns": [_column_attrs(c) for c in table.columns]},
        )
        nodes[table_key] = table_node
        for column in table.columns:
            col_key = _column_key(table.name, column.name)
            column_node = DocumentGraphNode(
                id=uuid.uuid4(),
                document_id=document.id,
                repository_id=document.repository_id,
                node_key=col_key,
                kind="column",
                name=f"{table.name}.{column.name}",
                attrs=_column_attrs(column),
            )
            nodes[col_key] = column_node

    for node in nodes.values():
        session.add(node)

    for table in graph.tables:
        table_node = nodes[_table_key(table.name)]
        for column in table.columns:
            column_node = nodes[_column_key(table.name, column.name)]
            edges.append(_edge(document, table_node, column_node, "has_column"))
            if column.is_pk:
                edges.append(_edge(document, table_node, column_node, "primary_key"))
            if column.target_table:
                target_key = _column_key(column.target_table, column.target_column or "")
                target_node = nodes.get(target_key)
                edges.append(
                    _edge(
                        document,
                        column_node,
                        target_node,
                        "foreign_key",
                        target_key=target_key if target_node is None else None,
                    )
                )
                target_table_node = nodes.get(_table_key(column.target_table))
                edges.append(
                    _edge(
                        document,
                        table_node,
                        target_table_node,
                        "references_table",
                        target_key=_table_key(column.target_table)
                        if target_table_node is None
                        else None,
                    )
                )

    for edge in edges:
        session.add(edge)


async def delete_document_graph(session: AsyncSession, document_id: uuid.UUID) -> None:
    await session.execute(
        delete(DocumentGraphEdge).where(DocumentGraphEdge.document_id == document_id)
    )
    await session.execute(
        delete(DocumentGraphNode).where(DocumentGraphNode.document_id == document_id)
    )


def graph_summary(table: DocumentGraphNode) -> str:
    """Render a table node as evidence text compatible with existing prompt rules."""
    attrs = table.attrs or {}
    pk = [str(item) for item in attrs.get("pk") or []]
    columns = [item for item in attrs.get("columns") or [] if isinstance(item, dict)]
    lines = [f"#### {table.name}"]
    if pk:
        lines.append(f"- PK: {', '.join(pk)}")
    lines.append("- Colunas:")
    for column in columns[:80]:
        name = str(column.get("name") or "")
        raw_type = str(column.get("raw_type") or "").strip()
        markers = []
        if column.get("is_pk"):
            markers.append("PK")
        if column.get("target_table"):
            target = f"{column.get('target_table')}.{column.get('target_column')}"
            markers.append(f"FK->{target}")
        suffix = " ".join(part for part in [raw_type, *markers] if part)
        lines.append(f"  - `{name}` {suffix}".rstrip())
    return "\n".join(lines)


def _parse_pk(section: str) -> list[str]:
    match = _PK_RE.search(section)
    if not match:
        return []
    return [_clean_identifier(part) for part in re.split(r",|\s+", match.group(1)) if part.strip()]


def _parse_columns(section: str, table_name: str, pk: list[str]) -> list[ParsedColumn]:
    pk_lower = {item.lower() for item in pk}
    columns: list[ParsedColumn] = []
    for match in _COLUMN_RE.finditer(section):
        name = _clean_identifier(match.group(1))
        rest = match.group(2).strip()
        target_table, target_column = _parse_fk(rest)
        raw_type = _clean_column_type(rest)
        columns.append(
            ParsedColumn(
                name=name,
                raw_type=raw_type,
                is_pk=name.lower() in pk_lower or _has_pk_marker(rest),
                target_table=target_table,
                target_column=target_column,
            )
        )
    return _dedupe_columns(columns, table_name)


def _parse_fk(rest: str) -> tuple[str | None, str | None]:
    match = _FK_RE.search(rest)
    if not match:
        return (None, None)
    parts = match.group(1).split(".")
    if len(parts) < 2:
        return (None, None)
    return (".".join(parts[:-1]), parts[-1])


def _clean_column_type(rest: str) -> str:
    rest = _FK_RE.sub("", rest)
    rest = re.sub(r"\bPK\b", "", rest, flags=re.IGNORECASE)
    return " ".join(rest.split())


def _normalise_table_name(value: str) -> str:
    value = value.strip().strip("`")
    return value if "." in value else f"dbo.{value}"


def _clean_identifier(value: str) -> str:
    return value.strip().strip("`*.,;:()[]")


def _has_pk_marker(rest: str) -> bool:
    return bool(re.search(r"\bPK\b", rest, re.IGNORECASE))


def _dedupe_columns(columns: list[ParsedColumn], table_name: str) -> list[ParsedColumn]:
    seen: set[str] = set()
    unique: list[ParsedColumn] = []
    for column in columns:
        key = f"{table_name}.{column.name}".lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(column)
    return unique


def _column_attrs(column: ParsedColumn) -> dict[str, Any]:
    return {
        "name": column.name,
        "raw_type": column.raw_type,
        "is_pk": column.is_pk,
        "target_table": column.target_table,
        "target_column": column.target_column,
    }


def _table_key(table_name: str) -> str:
    return f"table:{table_name.lower()}"


def _column_key(table_name: str, column_name: str) -> str:
    return f"column:{table_name.lower()}.{column_name.lower()}"


def _edge(
    document: Document,
    source: DocumentGraphNode,
    target: DocumentGraphNode | None,
    edge_type: str,
    *,
    target_key: str | None = None,
) -> DocumentGraphEdge:
    return DocumentGraphEdge(
        id=uuid.uuid4(),
        document_id=document.id,
        repository_id=document.repository_id,
        source_node_id=source.id,
        target_node_id=target.id if target else None,
        target_key=target_key,
        edge_type=edge_type,
        attrs={},
    )
