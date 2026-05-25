"""Regression tests for imported repository document evidence."""

from __future__ import annotations

from .agent_runtime_test_loader import evidence_docs as _evidence_docs
from .agent_runtime_test_loader import evidence_models as _evidence_models
from .agent_runtime_test_loader import evidence_prefetch as _evidence_prefetch
from .agent_runtime_test_loader import evidence_render as _evidence_render


def test_repository_document_queries_strip_prompt_context() -> None:
    queries = _evidence_docs._repo_doc_queries(
        ["SCHEMA BANCO DADOS ProdIndCbs"],
        "## Worktree\nignore este contexto\n\n## Mensagem do utilizador\n"
        "Use somente o documento importado SCHEMA BANCO DE DADOS para dbo.tgPrdProdSoli.",
    )

    assert queries[0].startswith("Use somente o documento importado")
    assert queries[1] == "dbo.tgPrdProdSoli"
    assert "## Worktree" not in queries[0]


def test_repository_document_summary_focuses_mentioned_table() -> None:
    summary = """#### dbo.tgPrdListPrec
- PK: EstaCod, ProdCod, LiPrCod
- Colunas:
  - `EstaCod` smallint PK

#### dbo.tgPrdProdSoli
- PK: PrSoCod
- Colunas:
  - `PrSoCod` int PK IDENT
  - `ProdIndCbsSoli` bit NULL

#### dbo.tgPrdProd
- PK: ProdCod
"""

    focused = _evidence_docs._focus_repo_doc_summary(
        summary,
        "Na tabela dbo.tgPrdProdSoli qual campo CBS aparece?",
    )

    assert "#### dbo.tgPrdProdSoli" in focused
    assert "PK: PrSoCod" in focused
    assert "ProdIndCbsSoli" in focused
    assert "tgPrdListPrec" not in focused


def test_repository_document_expansion_queries_follow_bare_table_mentions() -> None:
    queries = _evidence_docs._repo_doc_expansion_queries(
        [
            _evidence_models._DocHit(
                query="empresas ativas",
                title="DATABASE_SCHEMA_Edu_CBE_2.md (parte 4/246)",
                url="DATABASE_SCHEMA_Edu_CBE_2.md",
                summary="- **`tgGerEmpr`** — Empresa. PK `EmprCod`.",
                source="repository_document",
            )
        ],
        "Gere uma query para listar as empresas ativas",
    )

    assert queries[0] == "dbo.tgGerEmpr"


def test_repository_document_table_filter_ignores_foreign_key_mentions() -> None:
    summary = """#### dbo.tgPrdProdSoliAliq
- PK: PrSoCod, UnFeCod, AliqCod
- Colunas:
  - `PrSoCod` int PK FK->dbo.tgPrdProdSoli.PrSoCod
"""

    assert not _evidence_docs._matches_mentioned_table(
        summary,
        "Na tabela dbo.tgPrdProdSoli qual e a PK?",
    )


async def test_evidence_prefetch_searches_imported_repository_documents() -> None:
    calls: list[tuple[str, list[tuple[str, str]] | dict[str, str]]] = []

    class FakeResponse:
        status_code = 200

        def json(self) -> list[dict[str, str]]:
            return [
                {
                    "title": "SCHEMA BANCO DE DADOS (parte 42/246)",
                    "source_url": "DATABASE_SCHEMA_Edu_CBE_2.md",
                    "summary": "#### dbo.tgProProd\n- PK: ProdCod\n- ProdIndCbs: bit",
                }
            ]

    class FakeClient:
        async def get(self, url: str, params: list[tuple[str, str]] | dict[str, str]):
            calls.append((url, params))
            return FakeResponse()

    docs, attempts = await _evidence_docs._fetch_docs(
        FakeClient(),
        "http://sandbox:8080",
        [{"repo_id": "e41b15fa-5da8-4930-b741-ad3d2d859b45", "slug": "repo-demo"}],
        ["schema produtos CBS IBS"],
        user_message="qual tabela principal de produtos e campos CBS IBS?",
    )

    assert attempts == []
    assert docs[0].source == "repository_document"
    assert "/skills/search" in calls[0][0]
    assert ("repo_id", "e41b15fa-5da8-4930-b741-ad3d2d859b45") in calls[0][1]


async def test_evidence_prefetch_expands_imported_docs_to_discovered_table() -> None:
    calls: list[str] = []

    class FakeResponse:
        status_code = 200

        def __init__(self, query: str) -> None:
            self.query = query

        def json(self) -> list[dict[str, str]]:
            if self.query == "dbo.tgGerEmpr":
                return [
                    {
                        "title": "DATABASE_SCHEMA_Edu_CBE_2.md (parte 28/246)",
                        "source_url": "DATABASE_SCHEMA_Edu_CBE_2.md",
                        "summary": "#### dbo.tgGerEmpr\n- `EmprIndIna` bit\n",
                    }
                ]
            return [
                {
                    "title": "DATABASE_SCHEMA_Edu_CBE_2.md (parte 4/246)",
                    "source_url": "DATABASE_SCHEMA_Edu_CBE_2.md",
                    "summary": "- **`tgGerEmpr`** — Empresa. PK `EmprCod`.",
                }
            ]

    class FakeClient:
        async def get(self, url: str, params: list[tuple[str, str]] | dict[str, str]):
            del url
            query = next(value for key, value in params if key == "q")
            calls.append(query)
            return FakeResponse(query)

    docs, attempts = await _evidence_docs._fetch_docs(
        FakeClient(),
        "http://sandbox:8080",
        [{"repo_id": "e41b15fa-5da8-4930-b741-ad3d2d859b45", "slug": "repo-demo"}],
        ["empresas ativas"],
        user_message="Gere uma query para listar as empresas ativas",
    )

    assert attempts == []
    assert "dbo.tgGerEmpr" in calls
    assert "EmprIndIna" in docs[0].summary


def test_evidence_prefetch_prioritizes_imported_schema_for_sql_questions() -> None:
    assert _evidence_prefetch._should_prioritize_imported_schema(
        "Gere uma query para listar as empresas ativas",
        [
            _evidence_models._DocHit(
                query="dbo.tgGerEmpr",
                title="DATABASE_SCHEMA_Edu_CBE_2.md (parte 28/246)",
                url="DATABASE_SCHEMA_Edu_CBE_2.md",
                summary=(
                    "#### dbo.tgGerEmpr\n- PK: EstaCod, EmprCod\n- Colunas:\n  - `EmprIndIna` bit\n"
                ),
                source="repository_document",
            )
        ],
    )


def test_evidence_render_marks_imported_documents_as_repository_sources() -> None:
    section = _evidence_render._render_section(
        [
            _evidence_models._DocHit(
                query="schema produtos CBS IBS",
                title="SCHEMA BANCO DE DADOS (parte 42/246)",
                url="DATABASE_SCHEMA_Edu_CBE_2.md",
                summary="#### dbo.tgProProd\n- PK: ProdCod\n- ProdIndCbs: bit",
                source="repository_document",
            )
        ],
        [],
        [],
    )

    assert "documento importado" in section
    assert "priorize esses trechos" in section
    assert "DATABASE_SCHEMA_Edu_CBE_2.md" in section
    assert "Fontes consultadas" in section
