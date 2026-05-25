from __future__ import annotations

import re
from dataclasses import dataclass

from cappy_doc_import_extractor.ids import edge_id, materialized_doc_node_id
from cappy_doc_import_extractor.models import Graph, SourceDocument

DOC_FORMAT = "markdown_schema_catalog"
TABLE_HEADER_RE = re.compile(
    r"^####\s+(?P<schema>[\w-]+)\.(?P<table>[^\s(]+)\s*\((?P<rows>[\d.]+)\s+linhas\)\s*$"
)
PK_RE = re.compile(r"^\s*-\s+PK:\s*(?P<columns>.+?)\s*$", re.I)
COLUMN_RE = re.compile(r"^\s*-\s+`(?P<name>[^`]+)`\s+(?P<rest>.+?)\s*$")
FK_RE = re.compile(r"(?:\[FK->(?P<bracket>[^\]]+)\]|\bFK->(?P<plain>\S+))", re.I)


@dataclass(frozen=True)
class TableBlock:
    schema: str
    table: str
    row_count_hint: int
    line: int
    snippet: str
    pk_columns: frozenset[str] = frozenset()

    @property
    def qname(self) -> str:
        return f"{self.schema}.{self.table}"


@dataclass(frozen=True)
class PendingFk:
    source_id: str
    target_qname: str
    statement_line: int
    snippet: str
    chunk_index: int
    document_id: str


def parse_markdown_schema_catalog(
    *,
    graph: Graph,
    document: SourceDocument,
    repo_id: str,
    commit_sha: str,
) -> None:
    text = document.text
    lines = text.splitlines()
    document_id = _node_id(repo_id, commit_sha, document.id, "document", document.id)
    _add_document_node(graph, document, document_id)
    table_ids: dict[str, str] = {}
    column_ids: dict[str, str] = {}
    pending_fks: list[PendingFk] = []
    current: TableBlock | None = None

    for index, line in enumerate(lines, start=1):
        header = TABLE_HEADER_RE.match(line)
        if header:
            current = _table_block(header, index, line)
            table_id = _add_table_node(graph, document, repo_id, commit_sha, document_id, current)
            table_ids[current.qname] = table_id
            continue
        if line.startswith("### "):
            current = None
            continue
        if current is None:
            continue
        pk_match = PK_RE.match(line)
        if pk_match:
            current = TableBlock(
                schema=current.schema,
                table=current.table,
                row_count_hint=current.row_count_hint,
                line=current.line,
                snippet=current.snippet,
                pk_columns=frozenset(_split_columns(pk_match.group("columns"))),
            )
            continue
        if _ignorable_table_line(line):
            continue
        column = COLUMN_RE.match(line)
        if not column:
            _unmatched(graph, document, index, line)
            continue
        column_id, fk_target = _add_column_node(
            graph=graph,
            document=document,
            repo_id=repo_id,
            commit_sha=commit_sha,
            table=current,
            line=index,
            raw_line=line,
            name=column.group("name").strip(),
            rest=column.group("rest").strip(),
        )
        column_ids[_column_qname(current, column.group("name").strip())] = column_id
        graph.add_edge(
            edge_id=edge_id(table_ids[current.qname], "defines", column_id, None),
            source=table_ids[current.qname],
            target=column_id,
            edge_type="defines",
            evidence=_evidence(document, index, line),
            attrs=_edge_attrs(document, index),
        )
        if fk_target:
            pending_fks.append(
                PendingFk(
                    source_id=column_id,
                    target_qname=fk_target,
                    statement_line=index,
                    snippet=line[:240],
                    chunk_index=document.chunk_index_for_line(index),
                    document_id=document.id,
                )
            )

    _resolve_fks(graph, document, column_ids, pending_fks)


def _add_document_node(graph: Graph, document: SourceDocument, document_id: str) -> None:
    graph.add_node(
        node_id=document_id,
        kind="document",
        name=document.title,
        label=document.title,
        file_path=document.filename,
        line=1,
        line_end=max(1, document.text.count("\n") + 1),
        detail="Schema document",
        attrs={
            "document_id": document.id,
            "source_type": document.source_type,
            "doc_format": DOC_FORMAT,
            "chunks_count": document.chunks_count,
            "indexed_at": document.indexed_at,
        },
    )


def _add_table_node(
    graph: Graph,
    document: SourceDocument,
    repo_id: str,
    commit_sha: str,
    document_node_id: str,
    table: TableBlock,
) -> str:
    table_id = _node_id(repo_id, commit_sha, document.id, "table", table.qname)
    attrs = _node_attrs(document, table.line) | {
        "schema": table.schema,
        "row_count_hint": table.row_count_hint,
        "case_preserved": True,
    }
    graph.add_node(
        node_id=table_id,
        kind="table",
        name=table.qname,
        label=table.qname,
        file_path=document.filename,
        line=table.line,
        line_end=table.line,
        detail="Schema table from document",
        attrs=attrs,
    )
    graph.add_edge(
        edge_id=edge_id(document_node_id, "defines", table_id, None),
        source=document_node_id,
        target=table_id,
        edge_type="defines",
        evidence=_evidence(document, table.line, table.snippet),
        attrs=_edge_attrs(document, table.line),
    )
    return table_id


def _add_column_node(
    *,
    graph: Graph,
    document: SourceDocument,
    repo_id: str,
    commit_sha: str,
    table: TableBlock,
    line: int,
    raw_line: str,
    name: str,
    rest: str,
) -> tuple[str, str | None]:
    flags = _parse_flags(rest)
    is_pk = name in table.pk_columns or flags["pk"]
    qname = _column_qname(table, name)
    column_id = _node_id(repo_id, commit_sha, document.id, "column", qname)
    attrs = _node_attrs(document, line) | {
        "data_type": _data_type(rest),
        "is_nullable": flags["nullable"],
        "is_primary_key": is_pk,
        "case_preserved": True,
    }
    graph.add_node(
        node_id=column_id,
        kind="column",
        name=qname,
        label=name,
        file_path=document.filename,
        line=line,
        line_end=line,
        detail="Schema column from document",
        attrs=attrs,
    )
    return column_id, flags["fk_target"]


def _resolve_fks(
    graph: Graph,
    document: SourceDocument,
    column_ids: dict[str, str],
    pending_fks: list[PendingFk],
) -> None:
    for pending in pending_fks:
        target = column_ids.get(pending.target_qname)
        graph.add_edge(
            edge_id=edge_id(
                pending.source_id,
                "foreign_key",
                target,
                None if target else pending.target_qname,
            ),
            source=pending.source_id,
            target=target,
            target_external=None if target else f"table:{pending.target_qname}",
            edge_type="foreign_key",
            evidence=_evidence(document, pending.statement_line, pending.snippet),
            attrs={
                "document_id": pending.document_id,
                "chunk_index": pending.chunk_index,
            },
            confidence="high" if target else "medium",
        )


def _node_id(repo_id: str, commit_sha: str, document_id: str, kind: str, qname: str) -> str:
    return materialized_doc_node_id(
        repo_id=repo_id,
        commit_sha=commit_sha,
        document_id=document_id,
        kind=kind,
        qualified_name=qname,
    )


def _table_block(match: re.Match[str], line: int, snippet: str) -> TableBlock:
    rows = int(match.group("rows").replace(".", ""))
    return TableBlock(match.group("schema"), match.group("table"), rows, line, snippet[:240])


def _column_qname(table: TableBlock, column: str) -> str:
    return f"{table.schema}.{table.table}.{column}"


def _split_columns(raw: str) -> list[str]:
    return [part.strip().strip("`") for part in raw.split(",") if part.strip()]


def _parse_flags(rest: str) -> dict[str, str | bool | None]:
    fk_match = FK_RE.search(rest)
    return {
        "pk": bool(re.search(r"(?:\[PK\]|\bPK\b)", rest, re.I)),
        "nullable": bool(re.search(r"(?:\[NULL\]|\bNULL\b)", rest, re.I))
        and not bool(re.search(r"\bNOT\s+NULL\b", rest, re.I)),
        "fk_target": fk_match.group("bracket") or fk_match.group("plain") if fk_match else None,
    }


def _data_type(rest: str) -> str:
    cleaned = FK_RE.sub("", rest)
    cleaned = re.sub(r"\[(?:PK|NULL)\]", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\b(?:PK|NULL|IDENT)\b", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\bNOT\s*$", "", cleaned, flags=re.I)
    return " ".join(cleaned.split()).strip()


def _node_attrs(document: SourceDocument, line: int) -> dict[str, object]:
    return {
        "document_id": document.id,
        "chunk_index": document.chunk_index_for_line(line),
        "doc_format": DOC_FORMAT,
    }


def _edge_attrs(document: SourceDocument, line: int) -> dict[str, object]:
    return {
        "document_id": document.id,
        "chunk_index": document.chunk_index_for_line(line),
    }


def _evidence(document: SourceDocument, line: int, snippet: str) -> dict[str, object]:
    return {
        "file": document.filename,
        "line_start": line,
        "line_end": line,
        "snippet": snippet[:240],
    }


def _ignorable_table_line(line: str) -> bool:
    stripped = line.strip()
    return not stripped or stripped == "- Colunas:"


def _unmatched(graph: Graph, document: SourceDocument, line: int, raw_line: str) -> None:
    graph.diagnostic(
        document_id=document.id,
        level="info",
        code="unmatched_line",
        message=raw_line[:240],
        line=line,
        chunk_index=document.chunk_index_for_line(line),
    )
