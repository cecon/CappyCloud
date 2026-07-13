from __future__ import annotations

import uuid

from app.infrastructure.document_graph import (
    graph_summary,
    parse_document_graph,
    replace_document_graph,
)
from app.infrastructure.orm_models import Document
from app.infrastructure.orm_models_document_graph import DocumentGraphEdge, DocumentGraphNode


def test_parse_document_graph_extracts_table_columns_pk_and_fk() -> None:
    graph = parse_document_graph(
        """
#### dbo.tgFisVendItemImpo  (120 linhas)
- PK: EstaCod, VeDoCod, VeItSeq, TiImCod
- Colunas:
  - `EstaCod` smallint PK
  - `ProdCod` int FK->dbo.tgProProd.ProdCod
  - `TiImCod` tinyint FK->dbo.tgFisTipoImpo.TiImCod
"""
    )

    assert len(graph.tables) == 1
    table = graph.tables[0]
    assert table.name == "dbo.tgFisVendItemImpo"
    assert table.pk == ["EstaCod", "VeDoCod", "VeItSeq", "TiImCod"]
    assert table.columns[0].is_pk is True
    assert table.columns[1].target_table == "dbo.tgProProd"
    assert table.columns[1].target_column == "ProdCod"


def test_parse_document_graph_normalises_names_and_dedupes_columns() -> None:
    graph = parse_document_graph(
        """
#### tgProProd
- Colunas:
  - `ProdCod` int PK
  - `ProdCod` int PK
  - `ProdNome` varchar(80)
"""
    )

    assert len(graph.tables) == 1
    assert graph.tables[0].name == "dbo.tgProProd"
    assert [column.name for column in graph.tables[0].columns] == ["ProdCod", "ProdNome"]


def test_graph_summary_keeps_schema_shape_for_agent_evidence() -> None:
    node = DocumentGraphNode(
        node_key="table:dbo.tgprod",
        kind="table",
        name="dbo.tgProd",
        attrs={
            "pk": ["ProdCod"],
            "columns": [
                {"name": "ProdCod", "raw_type": "int", "is_pk": True},
                {
                    "name": "EstaCod",
                    "raw_type": "smallint",
                    "target_table": "dbo.tgEsta",
                    "target_column": "EstaCod",
                },
            ],
        },
    )

    summary = graph_summary(node)

    assert "#### dbo.tgProd" in summary
    assert "- PK: ProdCod" in summary
    assert "`EstaCod` smallint FK->dbo.tgEsta.EstaCod" in summary


async def test_replace_document_graph_materializes_nodes_edges_and_external_refs() -> None:
    session = _GraphSession()
    document = _document()

    await replace_document_graph(
        session,
        document,
        """
#### dbo.tgVenda
- PK: VendaCod
- Colunas:
  - `VendaCod` int PK
  - `ClienteCod` int FK->dbo.tgCliente.ClienteCod
""",
    )

    nodes = [item for item in session.added if isinstance(item, DocumentGraphNode)]
    edges = [item for item in session.added if isinstance(item, DocumentGraphEdge)]

    assert len(session.executed) == 2
    assert {node.kind for node in nodes} == {"table", "column"}
    assert {node.node_key for node in nodes} == {
        "table:dbo.tgvenda",
        "column:dbo.tgvenda.vendacod",
        "column:dbo.tgvenda.clientecod",
    }
    assert {edge.edge_type for edge in edges} == {
        "has_column",
        "primary_key",
        "foreign_key",
        "references_table",
    }
    assert any(edge.target_key == "column:dbo.tgcliente.clientecod" for edge in edges)
    assert any(edge.target_key == "table:dbo.tgcliente" for edge in edges)


async def test_replace_document_graph_skips_documents_without_schema_tables() -> None:
    session = _GraphSession()

    await replace_document_graph(session, _document(), "# Manual sem tabelas")

    assert len(session.executed) == 2
    assert session.added == []


class _GraphSession:
    def __init__(self) -> None:
        self.executed: list[object] = []
        self.added: list[object] = []

    async def execute(self, stmt):  # type: ignore[no-untyped-def]
        self.executed.append(stmt)

    def add(self, item: object) -> None:
        self.added.append(item)


def _document() -> Document:
    return Document(
        id=uuid.uuid4(),
        repository_id=uuid.uuid4(),
        title="DATABASE_SCHEMA_Edu_CBE_2.md",
        source_type="markdown",
        source_uri="file://DATABASE_SCHEMA_Edu_CBE_2.md",
        version=1,
        status="indexed",
        chunks_count=0,
    )
