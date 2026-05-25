from __future__ import annotations

import hashlib

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from cappy_sql_extractor.models import StatementText
from cappy_sql_extractor.names import column_name, sandbox_id, schema_part, table_name
from cappy_sql_extractor.statements import split_sql_statements


class SchemaEntityMixin:
    def _create_view(
        self,
        path: str,
        file_id: str,
        statement: StatementText,
        dialect: str,
        create: exp.Create,
    ) -> None:
        qname = table_name(create.this, dialect)
        node_id = sandbox_id(path, "view", qname)
        is_materialized = any(
            isinstance(item, exp.MaterializedProperty)
            for item in create.find_all(exp.MaterializedProperty)
        )
        definition = create.args.get("expression")
        normalized = (
            definition.sql(dialect=dialect) if definition is not None else statement.sql
        )
        self.graph.add_node(
            node_id=node_id,
            label=qname,
            kind="view",
            name=qname,
            path=path,
            statement=statement,
            detail="SQL view",
            attrs={
                "schema": schema_part(qname),
                "is_materialized": is_materialized,
                "view_definition_hash": hashlib.sha256(
                    normalized.encode("utf-8")
                ).hexdigest(),
            },
        )
        self.graph.add_edge(
            source=file_id,
            target=node_id,
            edge_type="defines",
            statement=statement,
            file_path=path,
        )
        self._references_tables(node_id, definition, path, statement, dialect)

    def _create_index(
        self,
        path: str,
        file_id: str,
        statement: StatementText,
        dialect: str,
        create: exp.Create,
    ) -> None:
        index = create.this
        if not isinstance(index, exp.Index):
            return
        table_qname = table_name(index.args.get("table"), dialect)
        index_name = column_name(index.this, dialect)
        qname = (
            f"{schema_part(table_qname)}.{index_name}"
            if schema_part(table_qname)
            else index_name
        )
        node_id = sandbox_id(path, "index", qname)
        self.graph.add_node(
            node_id=node_id,
            label=index_name,
            kind="index",
            name=qname,
            path=path,
            statement=statement,
            detail="SQL index",
            attrs={
                "schema": schema_part(qname),
                "is_unique": bool(create.args.get("unique")),
            },
        )
        self.graph.add_edge(
            source=file_id,
            target=node_id,
            edge_type="defines",
            statement=statement,
            file_path=path,
        )
        self._index_columns(node_id, table_qname, index, path, statement, dialect)

    def _index_columns(
        self,
        node_id: str,
        table_qname: str,
        index: exp.Index,
        path: str,
        statement: StatementText,
        dialect: str,
    ) -> None:
        params = index.args.get("params")
        columns = list(params.args.get("columns") or []) if params is not None else []
        for position, ordered in enumerate(columns):
            column = ordered.this if isinstance(ordered, exp.Ordered) else ordered
            col_name = column_name(column, dialect)
            target = self.column_nodes.get((table_qname, col_name))
            self.graph.add_edge(
                source=node_id,
                target=target,
                target_external=None if target else f"column:{table_qname}.{col_name}",
                edge_type="indexes",
                statement=statement,
                file_path=path,
                confidence="high" if target else "medium",
                attrs={"position": position},
            )

    def _create_routine(
        self,
        path: str,
        file_id: str,
        statement: StatementText,
        dialect: str,
        create: exp.Create,
        routine_kind: str,
    ) -> None:
        qname = _routine_name(create.this, dialect)
        node_id = sandbox_id(path, "stored_procedure", qname)
        self.graph.add_node(
            node_id=node_id,
            label=qname,
            kind="stored_procedure",
            name=qname,
            path=path,
            statement=statement,
            detail="SQL routine",
            attrs={"schema": schema_part(qname), "routine_kind": routine_kind.lower()},
        )
        self.graph.add_edge(
            source=file_id,
            target=node_id,
            edge_type="defines",
            statement=statement,
            file_path=path,
        )
        expression = create.args.get("expression")
        self._references_tables(node_id, expression, path, statement, dialect)
        if isinstance(expression, exp.Heredoc):
            self._references_tables_from_sql(
                node_id, str(expression.this or ""), path, statement, dialect
            )

    def _create_trigger(
        self,
        path: str,
        file_id: str,
        statement: StatementText,
        dialect: str,
        create: exp.Create,
    ) -> None:
        name = column_name(create.this, dialect)
        node_id = sandbox_id(path, "trigger", name)
        self.graph.add_node(
            node_id=node_id,
            label=name,
            kind="trigger",
            name=name,
            path=path,
            statement=statement,
            detail="SQL trigger",
            attrs={},
        )
        self.graph.add_edge(
            source=file_id,
            target=node_id,
            edge_type="defines",
            statement=statement,
            file_path=path,
        )
        for prop in create.find_all(exp.TriggerProperties):
            table = prop.args.get("table")
            if table is not None:
                self._add_table_reference(
                    node_id, table_name(table, dialect), path, statement
                )

    def _references_tables(
        self,
        source_id: str,
        expression: exp.Expression | None,
        path: str,
        statement: StatementText,
        dialect: str,
    ) -> None:
        if expression is None:
            return
        for table in expression.find_all(exp.Table):
            qname = table_name(table, dialect)
            if qname:
                self._add_table_reference(source_id, qname, path, statement)

    def _references_tables_from_sql(
        self,
        source_id: str,
        sql: str,
        path: str,
        statement: StatementText,
        dialect: str,
    ) -> None:
        for body_statement in split_sql_statements(sql):
            try:
                parsed = sqlglot.parse_one(body_statement.sql, read=dialect)
            except ParseError:
                continue
            self._references_tables(source_id, parsed, path, statement, dialect)

    def _add_table_reference(
        self, source_id: str, qname: str, path: str, statement: StatementText
    ) -> None:
        target = self.table_nodes.get(qname)
        self.graph.add_edge(
            source=source_id,
            target=target,
            target_external=None if target else f"table:{qname}",
            edge_type="references_table",
            statement=statement,
            file_path=path,
            confidence="high" if target else "medium",
        )

    def _resolve_pending_fks(self) -> None:
        for pending in self.pending_fks:
            target = self.column_nodes.get(
                (pending.target_table, pending.target_column)
            )
            self.graph.add_edge(
                source=pending.source,
                target=target,
                target_external=None
                if target
                else f"table:{pending.target_table}.{pending.target_column}",
                edge_type="foreign_key",
                statement=pending.statement,
                file_path=pending.file_path,
                confidence="high" if target else "medium",
            )


def _routine_name(expression: exp.Expression, dialect: str) -> str:
    if isinstance(expression, exp.UserDefinedFunction):
        inner = expression.this
        if isinstance(inner, exp.Table):
            return table_name(inner, dialect)
        return column_name(inner, dialect)
    return (
        table_name(expression, dialect)
        if isinstance(expression, exp.Table)
        else column_name(expression, dialect)
    )
