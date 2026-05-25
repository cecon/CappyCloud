"""Regression tests for repo context and evidence prompt behavior."""

from __future__ import annotations

from typing import Any

from .agent_runtime_test_loader import (
    agent_context as _agent_context,
)
from .agent_runtime_test_loader import (
    agent_prompt_sections as _agent_prompt_sections,
)
from .agent_runtime_test_loader import (
    evidence_docs as _evidence_docs,
)
from .agent_runtime_test_loader import (
    evidence_models as _evidence_models,
)
from .agent_runtime_test_loader import (
    evidence_prefetch as _evidence_prefetch,
)
from .agent_runtime_test_loader import (
    evidence_render as _evidence_render,
)
from .agent_runtime_test_loader import (
    evidence_terms as _evidence_terms,
)


def test_session_tools_scope_skill_search_by_repo_id() -> None:
    section = _agent_prompt_sections.render_session_tools(
        "http://sandbox:8080",
        repos=[{"repo_id": "2d9500d8-eb4c-4535-9b5c-5d0b4e7bd6cc"}],
    )

    assert "repo_id=2d9500d8-eb4c-4535-9b5c-5d0b4e7bd6cc" in section


def test_session_tools_require_confluence_for_operational_support() -> None:
    section = _agent_prompt_sections.render_session_tools(
        "http://sandbox:8080",
        repos=[
            {
                "alias": "autosystem",
                "confluence_url": "https://share.linx.com.br",
                "confluence_space": "Postos",
                "confluence_labels": ["autosystem"],
            }
        ],
    )

    assert "consulta é obrigatória para perguntas de suporte operacional" in section
    assert "execute primeiro o `curl` de `/confluence/search`" in section
    assert "A busca principal deve manter `&space=`" in section
    assert "resultados forem vazios, lentos ou pouco aderentes" in section
    assert "&space=Postos" in section
    assert "&labels=autosystem" in section


def test_response_rules_treat_grep_as_candidate_not_evidence() -> None:
    section = _agent_prompt_sections.render_response_rules()

    assert "`Grep`, listagem de arquivos" in section
    assert "não são evidência suficiente" in section
    assert "Não invente nomes de colunas" in section
    assert "Não recomende criar script novo" in section
    assert "Não adicione prefixos como `src/`" in section


def test_build_prompt_injects_repo_architect_agent_before_skills() -> None:
    prompt = _agent_context.build_prompt_with_agent(
        "Como funciona o fiscal?",
        skills=[{"title": "AutoSystem Fiscal", "summary": "Fiscal", "content": "Skill"}],
        sandbox_session_url="http://sandbox:8080",
        repos=[{"slug": "autosystem", "worktree_path": "/repos/sessions/abc/autosystem"}],
        agent_profiles=[
            {
                "slug": "autosystem-architect",
                "name": "AutoSystem Architect",
                "description": "Arquitetura AutoSystem",
                "system_prompt": "Mapa de investigação AutoSystem",
                "default_model": None,
            }
        ],
    )

    assert "## Agente arquitetural do repositório" in prompt
    assert prompt.index("AutoSystem Architect") < prompt.index("## Skills configuradas")
    assert "Mapa de investigação AutoSystem" in prompt


async def test_load_repo_agent_profiles_uses_sandbox_agents_by_repo_slug(
    monkeypatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeConn:
        async def fetch(
            self,
            query: str,
            sandbox_id: str,
            agent_names: list[str],
        ) -> list[dict[str, Any]]:
            captured["query"] = query
            captured["sandbox_id"] = sandbox_id
            captured["agent_names"] = agent_names
            return [
                {
                    "name": "seller-architect",
                    "description": "desc",
                    "system_prompt": "prompt",
                    "model": "",
                }
            ]

        async def close(self) -> None:
            captured["closed"] = True

    async def fake_connect(database_url: str) -> FakeConn:
        captured["database_url"] = database_url
        return FakeConn()

    monkeypatch.setattr(_agent_context.asyncpg, "connect", fake_connect)

    profiles = await _agent_context.load_repo_agent_profiles(
        "postgresql://db",
        [{"slug": "Seller"}, {"slug": "Seller"}],
        sandbox_id="1cf4ffe6-97b4-497d-a482-e533b2535417",
    )

    assert captured["sandbox_id"] == "1cf4ffe6-97b4-497d-a482-e533b2535417"
    assert captured["agent_names"] == ["seller-architect"]
    assert "FROM sandbox_agents" in captured["query"]
    assert "lower(name) = ANY" in captured["query"]
    assert profiles[0]["name"] == "seller-architect"
    assert captured["closed"] is True


def test_evidence_terms_prioritize_ticketlog_recolha_context() -> None:
    terms = _evidence_terms._terms_for(
        "Temos um cliente com recolha de notas da TicketLog. Estavam usando "
        "motivo de movimentação errado, que não era parametrizado para TicketLog. "
        "Corrigimos o motivo de movimentação, como fazer para reenviar as vendas antigas?"
    )

    assert terms[:2] == ["TicketLog recolha notas", "recolha notas TicketLog"]
    assert "Estavam usando motivo de" not in terms


def test_evidence_terms_ignore_sql_request_filler_words() -> None:
    terms = _evidence_terms._terms_for("Gere uma query para listar as empresas ativas")

    assert "empresas" in terms
    assert "ativas" in terms
    assert "empresas ativas" in terms
    assert "Gere" not in terms
    assert "uma" not in terms
    assert "query" not in terms
    assert "listar as empresas ativas" not in terms


def test_repository_document_queries_strip_prompt_context() -> None:
    queries = _evidence_docs._repo_doc_queries(
        ["SCHEMA BANCO DADOS ProdIndCbs"],
        "## Worktree\nignore este contexto\n\n## Mensagem do utilizador\n"
        "Use somente o documento importado SCHEMA BANCO DE DADOS para dbo.tgPrdProdSoli.",
    )

    assert (
        queries[0]
        == "Use somente o documento importado SCHEMA BANCO DE DADOS para dbo.tgPrdProdSoli."
    )
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
    assert "PK: ProdCod" not in focused


def test_repository_document_expansion_queries_follow_bare_table_mentions() -> None:
    queries = _evidence_docs._repo_doc_expansion_queries(
        [
            _evidence_models._DocHit(
                query="empresas ativas",
                title="DATABASE_SCHEMA_Edu_CBE_2.md (parte 4/246)",
                url="DATABASE_SCHEMA_Edu_CBE_2.md",
                summary=(
                    "- **`tgGerEmpr`** — Empresa. PK `EmprCod`.\n"
                    "- **`tgGerEsta`** — Estabelecimento/loja."
                ),
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

    assert (
        _evidence_docs._matches_mentioned_table(
            summary,
            "Na tabela dbo.tgPrdProdSoli qual e a PK?",
        )
        is False
    )


async def test_evidence_prefetch_searches_confluence_space_before_labels() -> None:
    calls: list[dict[str, str]] = []

    class FakeResponse:
        status_code = 200

        def json(self) -> dict[str, list[dict[str, str]]]:
            return {
                "results": [
                    {
                        "title": "PDV Fácil + AS3 | Caixa - Integração Recolha de Notas",
                        "url": "https://share.linx.com.br/pages/viewpage.action?pageId=555785211",
                        "summary": "TicketLog/Frota",
                    }
                ]
            }

    class FakeClient:
        async def get(self, url: str, params: dict[str, str]) -> FakeResponse:
            calls.append(dict(params))
            return FakeResponse()

    docs, attempts = await _evidence_docs._fetch_docs(
        FakeClient(),
        "http://sandbox:8080",
        [
            {
                "confluence_url": "https://share.linx.com.br",
                "confluence_space": "Postos",
                "confluence_labels": ["autosystem"],
            }
        ],
        ["TicketLog recolha notas"],
    )

    assert docs[0].title.startswith("PDV Fácil")
    assert calls == [
        {
            "base_url": "https://share.linx.com.br",
            "q": "TicketLog recolha notas",
            "limit": "3",
            "space": "Postos",
        }
    ]
    assert attempts[0].source.labels == ()


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
        async def get(
            self,
            url: str,
            params: list[tuple[str, str]] | dict[str, str],
        ) -> FakeResponse:
            calls.append((url, params))
            return FakeResponse()

    docs, attempts = await _evidence_docs._fetch_docs(
        FakeClient(),
        "http://sandbox:8080",
        [{"repo_id": "e41b15fa-5da8-4930-b741-ad3d2d859b45", "slug": "Seller"}],
        ["schema produtos CBS IBS"],
        user_message="qual tabela principal de produtos e campos CBS IBS?",
    )

    assert attempts == []
    assert docs[0].source == "repository_document"
    assert docs[0].title.startswith("SCHEMA BANCO DE DADOS")
    assert docs[0].url == "DATABASE_SCHEMA_Edu_CBE_2.md"
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
                        "summary": (
                            "#### dbo.tgGerEmpr  (5 linhas)\n"
                            "- PK: EstaCod, EmprCod\n"
                            "- Colunas:\n"
                            "  - `EmprCod` smallint PK\n"
                            "  - `EmprRazSoc` varchar(65)\n"
                            "  - `EmprIndIna` bit\n"
                        ),
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
        async def get(
            self,
            url: str,
            params: list[tuple[str, str]] | dict[str, str],
        ) -> FakeResponse:
            del url
            query = ""
            if isinstance(params, list):
                query = next(value for key, value in params if key == "q")
            calls.append(query)
            return FakeResponse(query)

    docs, attempts = await _evidence_docs._fetch_docs(
        FakeClient(),
        "http://sandbox:8080",
        [{"repo_id": "e41b15fa-5da8-4930-b741-ad3d2d859b45", "slug": "Seller"}],
        ["empresas ativas"],
        user_message="Gere uma query para listar as empresas ativas",
    )

    assert attempts == []
    assert "dbo.tgGerEmpr" in calls
    assert docs[0].title == "DATABASE_SCHEMA_Edu_CBE_2.md (parte 28/246)"
    assert "EmprIndIna" in docs[0].summary


def test_evidence_prefetch_prioritizes_imported_schema_for_sql_questions() -> None:
    assert (
        _evidence_prefetch._should_prioritize_imported_schema(
            "Gere uma query para listar as empresas ativas",
            [
                _evidence_models._DocHit(
                    query="dbo.tgGerEmpr",
                    title="DATABASE_SCHEMA_Edu_CBE_2.md (parte 28/246)",
                    url="DATABASE_SCHEMA_Edu_CBE_2.md",
                    summary=(
                        "#### dbo.tgGerEmpr\n"
                        "- PK: EstaCod, EmprCod\n"
                        "- Colunas:\n"
                        "  - `EmprIndIna` bit\n"
                    ),
                    source="repository_document",
                )
            ],
        )
        is True
    )


def test_evidence_render_requires_confluence_sources_in_final_answer() -> None:
    section = _evidence_render._render_section(
        [
            _evidence_models._DocHit(
                query="TicketLog recolha notas",
                title="PDV Fácil + AS3 | Caixa - Integração Recolha de Notas",
                url="https://share.linx.com.br/pages/viewpage.action?pageId=555785211",
                summary="Integração TicketLog/Frota",
            )
        ],
        [],
        [],
    )

    assert "Fontes consultadas" in section
    assert "Não omita a fonte documental" in section
    assert "PDV Fácil + AS3" in section


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
    assert "não responda que o documento não foi localizado" in section
    assert "não misture PKs ou colunas de tabelas vizinhas" in section
    assert "DATABASE_SCHEMA_Edu_CBE_2.md" in section
    assert "Fontes consultadas" in section
