from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from cappy_sql_extractor.dialects import file_dialect
from cappy_sql_extractor.files import relative_path
from cappy_sql_extractor.models import Graph, StatementText
from cappy_sql_extractor.names import sandbox_id
from cappy_sql_extractor.schema_entities import SchemaEntityMixin
from cappy_sql_extractor.statements import split_sql_statements
from cappy_sql_extractor.table_entities import TableEntityMixin


@dataclass(frozen=True)
class PendingFk:
    source: str
    target_table: str
    target_column: str
    statement: StatementText
    file_path: str


class SqlExtractor(TableEntityMixin, SchemaEntityMixin):
    def __init__(self, repo: Path, repo_dialect: str) -> None:
        self.repo = repo
        self.repo_dialect = repo_dialect
        self.graph = Graph()
        self.table_nodes: dict[str, str] = {}
        self.column_nodes: dict[tuple[str, str], str] = {}
        self.pending_fks: list[PendingFk] = []

    def extract(self, files: list[Path]) -> Graph:
        for file in files:
            self._extract_file(file)
        self._resolve_pending_fks()
        return self.graph

    def _extract_file(self, file: Path) -> None:
        path = relative_path(self.repo, file)
        dialect = file_dialect(file, self.repo_dialect)
        text = file.read_text(encoding="utf-8", errors="ignore")
        file_statement = StatementText(
            sql=path, line_start=1, line_end=max(1, text.count("\n") + 1)
        )
        file_id = sandbox_id(path, "sql_file", path)
        self.graph.add_node(
            node_id=file_id,
            label=Path(path).name,
            kind="sql_file",
            name=path,
            path=path,
            statement=file_statement,
            detail="SQL file",
            attrs={"dialect": dialect},
        )

        for statement in split_sql_statements(text):
            try:
                parsed = sqlglot.parse_one(statement.sql, read=dialect)
            except ParseError as exc:
                self.graph.diagnostic(
                    level="warning",
                    phase="parse",
                    file_path=path,
                    line=statement.line_start,
                    message=str(exc),
                )
                continue
            if isinstance(parsed, exp.Create):
                self._extract_create(path, file_id, statement, dialect, parsed)

    def _extract_create(
        self,
        path: str,
        file_id: str,
        statement: StatementText,
        dialect: str,
        create: exp.Create,
    ) -> None:
        kind = str(create.args.get("kind") or "").upper()
        if kind == "TABLE":
            self._create_table(path, file_id, statement, dialect, create)
        elif kind == "VIEW":
            self._create_view(path, file_id, statement, dialect, create)
        elif kind == "INDEX":
            self._create_index(path, file_id, statement, dialect, create)
        elif kind in {"FUNCTION", "PROCEDURE"}:
            self._create_routine(path, file_id, statement, dialect, create, kind)
        elif kind == "TRIGGER":
            self._create_trigger(path, file_id, statement, dialect, create)
