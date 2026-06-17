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


def test_agent_prompt_does_not_instruct_read_tool_for_file_evidence() -> None:
    prompt = _agent_context.build_prompt_with_agent(
        "qual a stack desse repo?",
        skills=[],
        sandbox_session_url="http://sandbox:8080",
        repos=[
            {
                "slug": "Seller",
                "worktree_path": "/repos/sessions/abc/Seller",
                "confluence_url": "https://share.linx.com.br",
                "confluence_space": "Postos",
            }
        ],
    )

    assert "sed -n" in prompt
    for forbidden in (
        "Grep/Read",
        "Grep e Read",
        "Bash/Grep/Read",
        "`Read`",
        "'Read...'",
    ):
        assert forbidden not in prompt


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
