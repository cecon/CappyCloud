from __future__ import annotations

from typing import Any

from sqlglot import exp

from cappy_sql_extractor.models import StatementText
from cappy_sql_extractor.names import column_name, sandbox_id, schema_part, table_name


class TableEntityMixin:
    def _create_table(
        self,
        path: str,
        file_id: str,
        statement: StatementText,
        dialect: str,
        create: exp.Create,
    ) -> None:
        schema = create.this
        if not isinstance(schema, exp.Schema):
            return
        table_qname = table_name(schema.this, dialect)
        table_id = sandbox_id(path, "table", table_qname)
        self.table_nodes[table_qname] = table_id
        self.graph.add_node(
            node_id=table_id,
            label=table_qname,
            kind="table",
            name=table_qname,
            path=path,
            statement=statement,
            detail="SQL table",
            attrs={
                "schema": schema_part(table_qname),
                "is_temporary": "TEMP" in statement.sql.upper(),
                "is_external": False,
            },
        )
        self.graph.add_edge(
            source=file_id,
            target=table_id,
            edge_type="defines",
            statement=statement,
            file_path=path,
        )
        constraints = self._table_constraints(schema, dialect)
        self._create_columns(
            path, table_id, table_qname, statement, dialect, schema, constraints
        )
        self._create_constraints(path, table_id, table_qname, statement, constraints)

    def _create_columns(
        self,
        path: str,
        table_id: str,
        table_qname: str,
        statement: StatementText,
        dialect: str,
        schema: exp.Schema,
        constraints: dict[str, Any],
    ) -> None:
        for item in schema.expressions:
            if not isinstance(item, exp.ColumnDef):
                continue
            col_name = column_name(item.this, dialect)
            column_id = sandbox_id(path, "column", f"{table_qname}.{col_name}")
            self.column_nodes[(table_qname, col_name)] = column_id
            column_constraints = item.args.get("constraints") or []
            default = _default_expr(column_constraints, dialect)
            kind = item.args.get("kind")
            self.graph.add_node(
                node_id=column_id,
                label=col_name,
                kind="column",
                name=f"{table_qname}.{col_name}",
                path=path,
                statement=statement,
                detail="SQL column",
                attrs={
                    "data_type": kind.sql(dialect=dialect) if kind is not None else "",
                    "is_nullable": not _has_constraint(
                        column_constraints, exp.NotNullColumnConstraint
                    ),
                    "is_primary_key": col_name in constraints["pk"]
                    or _has_constraint(
                        column_constraints, exp.PrimaryKeyColumnConstraint
                    ),
                    "is_unique": col_name in constraints["unique"]
                    or _has_constraint(column_constraints, exp.UniqueColumnConstraint),
                    "has_default": default is not None,
                    "default_expr": default,
                },
            )
            self.graph.add_edge(
                source=table_id,
                target=column_id,
                edge_type="defines",
                statement=statement,
                file_path=path,
            )
            self._inline_constraints(
                path, table_id, table_qname, col_name, item, statement, dialect
            )

    def _inline_constraints(
        self,
        path: str,
        table_id: str,
        table_qname: str,
        col_name: str,
        column: exp.ColumnDef,
        statement: StatementText,
        dialect: str,
    ) -> None:
        from cappy_sql_extractor.extractor import PendingFk

        for constraint in column.args.get("constraints") or []:
            kind = constraint.args.get("kind")
            if isinstance(kind, exp.PrimaryKeyColumnConstraint):
                self._constraint_node(
                    path, table_id, f"{table_qname}.{col_name}.pk", "pk", statement
                )
            elif isinstance(kind, exp.UniqueColumnConstraint):
                self._constraint_node(
                    path,
                    table_id,
                    f"{table_qname}.{col_name}.unique",
                    "unique",
                    statement,
                )
            elif isinstance(kind, exp.Reference):
                target_table, target_column = _reference_target(kind, dialect)
                if target_table and target_column:
                    source = self.column_nodes[(table_qname, col_name)]
                    self.pending_fks.append(
                        PendingFk(source, target_table, target_column, statement, path)
                    )
                    self._constraint_node(
                        path, table_id, f"{table_qname}.{col_name}.fk", "fk", statement
                    )

    def _create_constraints(
        self,
        path: str,
        table_id: str,
        table_qname: str,
        statement: StatementText,
        constraints: dict[str, Any],
    ) -> None:
        from cappy_sql_extractor.extractor import PendingFk

        for name, kind in constraints["nodes"]:
            self._constraint_node(path, table_id, name, kind, statement)
        for source_col, target_table, target_col in constraints["fks"]:
            source_id = self.column_nodes.get((table_qname, source_col))
            if source_id:
                self.pending_fks.append(
                    PendingFk(source_id, target_table, target_col, statement, path)
                )

    def _table_constraints(self, schema: exp.Schema, dialect: str) -> dict[str, Any]:
        result: dict[str, Any] = {"pk": set(), "unique": set(), "fks": [], "nodes": []}
        table_qname = table_name(schema.this, dialect)
        for item in schema.expressions:
            constraint_name = ""
            expressions: list[exp.Expression] = [item]
            if isinstance(item, exp.Constraint):
                constraint_name = str(item.this.name if item.this is not None else "")
                expressions = list(item.expressions)
            for expression in expressions:
                _collect_constraint(
                    result, expression, table_qname, constraint_name, dialect
                )
        return result

    def _constraint_node(
        self,
        path: str,
        table_id: str,
        name: str,
        constraint_kind: str,
        statement: StatementText,
    ) -> None:
        node_id = sandbox_id(path, "constraint", name)
        self.graph.add_node(
            node_id=node_id,
            label=name.split(".")[-1],
            kind="constraint",
            name=name,
            path=path,
            statement=statement,
            detail="SQL constraint",
            attrs={"constraint_kind": constraint_kind},
        )
        self.graph.add_edge(
            source=table_id,
            target=node_id,
            edge_type="defines",
            statement=statement,
            file_path=path,
        )


def _collect_constraint(
    result: dict[str, Any],
    expression: exp.Expression,
    table_qname: str,
    constraint_name: str,
    dialect: str,
) -> None:
    if isinstance(expression, exp.PrimaryKey):
        columns = [column_name(column, dialect) for column in expression.expressions]
        result["pk"].update(columns)
        result["nodes"].append((constraint_name or f"{table_qname}.pk", "pk"))
    elif isinstance(expression, exp.ForeignKey):
        target_table, target_column = _reference_target(
            expression.args.get("reference"), dialect
        )
        for source in expression.expressions:
            source_col = column_name(source, dialect)
            if target_table and target_column:
                result["fks"].append((source_col, target_table, target_column))
        result["nodes"].append((constraint_name or f"{table_qname}.fk", "fk"))
    elif isinstance(expression, exp.UniqueColumnConstraint):
        columns = [
            column_name(column, dialect) for column in _constraint_columns(expression)
        ]
        result["unique"].update(columns)
        result["nodes"].append((constraint_name or f"{table_qname}.unique", "unique"))
    elif isinstance(expression, exp.CheckColumnConstraint):
        result["nodes"].append(
            (constraint_name or f"{table_qname}.check.{len(result['nodes'])}", "check")
        )


def _has_constraint(
    constraints: list[exp.Expression], constraint_type: type[exp.Expression]
) -> bool:
    return any(
        isinstance(item.args.get("kind"), constraint_type) for item in constraints
    )


def _default_expr(constraints: list[exp.Expression], dialect: str) -> str | None:
    for item in constraints:
        kind = item.args.get("kind")
        if isinstance(kind, exp.DefaultColumnConstraint):
            return (kind.this.sql(dialect=dialect) if kind.this is not None else "")[
                :240
            ]
    return None


def _reference_target(
    reference: exp.Expression | None, dialect: str
) -> tuple[str, str]:
    if isinstance(reference, exp.Reference):
        reference = reference.this
    if not isinstance(reference, exp.Schema):
        return "", ""
    target_table = table_name(reference.this, dialect)
    target_column = (
        column_name(reference.expressions[0], dialect)
        if reference.expressions
        else "id"
    )
    return target_table, target_column


def _constraint_columns(expression: exp.Expression) -> list[exp.Expression]:
    schema = expression.args.get("this")
    if isinstance(schema, exp.Schema):
        return list(schema.expressions)
    return list(expression.expressions)
