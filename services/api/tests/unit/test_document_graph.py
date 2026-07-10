from __future__ import annotations

from app.infrastructure.document_graph import graph_summary, parse_document_graph
from app.infrastructure.orm_models_document_graph import DocumentGraphNode


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
