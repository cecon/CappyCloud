"""Regression tests for CappyCloud agent runtime edge cases."""

from __future__ import annotations

import asyncio
import sys
import types
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from importlib import util
from pathlib import Path
from typing import Any


def _find_repo_root() -> Path:
    current = Path(__file__).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "services" / "cappycloud_agent").is_dir():
            return candidate
    raise RuntimeError("Não encontrei services/cappycloud_agent no worktree.")


ROOT = _find_repo_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_agent_pkg = types.ModuleType("services.cappycloud_agent")
_agent_pkg.__path__ = [str(ROOT / "services/cappycloud_agent")]  # type: ignore[attr-defined]
sys.modules.setdefault("services.cappycloud_agent", _agent_pkg)


def _load_module(name: str, path: Path) -> types.ModuleType:
    spec = util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_agent_context = _load_module(
    "services.cappycloud_agent._agent_context",
    ROOT / "services/cappycloud_agent/_agent_context.py",
)
_agent_prompt_sections = _load_module(
    "services.cappycloud_agent._agent_prompt_sections",
    ROOT / "services/cappycloud_agent/_agent_prompt_sections.py",
)
_pipeline_helpers = _load_module(
    "services.cappycloud_agent._pipeline_helpers",
    ROOT / "services/cappycloud_agent/_pipeline_helpers.py",
)
_pipeline_event_stream = _load_module(
    "services.cappycloud_agent._pipeline_event_stream",
    ROOT / "services/cappycloud_agent/_pipeline_event_stream.py",
)
_grpc_event_handlers = _load_module(
    "services.cappycloud_agent._grpc_event_handlers",
    ROOT / "services/cappycloud_agent/_grpc_event_handlers.py",
)
_assistant_output = _load_module(
    "services.cappycloud_agent._assistant_output",
    ROOT / "services/cappycloud_agent/_assistant_output.py",
)
_task_final_message = _load_module(
    "services.cappycloud_agent._task_final_message",
    ROOT / "services/cappycloud_agent/_task_final_message.py",
)
_evidence_terms = _load_module(
    "services.cappycloud_agent._evidence_terms",
    ROOT / "services/cappycloud_agent/_evidence_terms.py",
)
_evidence_docs = _load_module(
    "services.cappycloud_agent._evidence_docs",
    ROOT / "services/cappycloud_agent/_evidence_docs.py",
)
_evidence_models = _load_module(
    "services.cappycloud_agent._evidence_models",
    ROOT / "services/cappycloud_agent/_evidence_models.py",
)
_evidence_render = _load_module(
    "services.cappycloud_agent._evidence_render",
    ROOT / "services/cappycloud_agent/_evidence_render.py",
)


async def test_push_mcp_config_reads_enabled_mcps_by_sandbox(monkeypatch) -> None:
    sandbox_id = uuid.uuid4()
    captured: dict[str, Any] = {}

    class FakeConn:
        async def fetch(self, query: str, arg: uuid.UUID) -> list[dict[str, Any]]:
            captured["query"] = query
            captured["arg"] = arg
            return [
                {
                    "name": "github",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "env": {"GITHUB_TOKEN": "token"},
                }
            ]

        async def close(self) -> None:
            captured["closed"] = True

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            pass

        async def post(self, url: str, json: dict) -> types.SimpleNamespace:
            captured["url"] = url
            captured["json"] = json
            return types.SimpleNamespace(status_code=200)

    async def fake_connect(database_url: str) -> FakeConn:
        captured["database_url"] = database_url
        return FakeConn()

    monkeypatch.setattr(_pipeline_helpers.asyncpg, "connect", fake_connect)
    monkeypatch.setattr(_pipeline_helpers.httpx, "AsyncClient", FakeAsyncClient)

    await _pipeline_helpers.push_mcp_config(
        "postgresql://db", str(sandbox_id), "http://sandbox:8080"
    )

    assert "sandbox_id = $1" in captured["query"]
    assert "user_id" not in captured["query"]
    assert captured["arg"] == sandbox_id
    assert captured["url"] == "http://sandbox:8080/mcp/configure"
    assert captured["json"]["mcpServers"]["github"]["command"] == "npx"
    assert captured["closed"] is True


async def test_has_enabled_signoz_mcp_reads_by_sandbox(monkeypatch) -> None:
    sandbox_id = uuid.uuid4()
    captured: dict[str, Any] = {}

    class FakeConn:
        async def fetchrow(self, query: str, arg: uuid.UUID) -> dict[str, int]:
            captured["query"] = query
            captured["arg"] = arg
            return {"?column?": 1}

        async def close(self) -> None:
            pass

    async def fake_connect(database_url: str) -> FakeConn:
        captured["database_url"] = database_url
        return FakeConn()

    monkeypatch.setattr(_pipeline_helpers.asyncpg, "connect", fake_connect)

    assert await _pipeline_helpers.has_enabled_signoz_mcp("postgresql://db", str(sandbox_id))
    assert "sandbox_id = $1" in captured["query"]
    assert "user_id" not in captured["query"]
    assert captured["arg"] == sandbox_id


def test_stream_task_events_keeps_connection_alive_on_empty_queue(monkeypatch) -> None:
    class FakeQueue:
        def __init__(self) -> None:
            self.calls = 0

        def get(self, timeout: int):
            self.calls += 1
            if self.calls == 1:
                raise _pipeline_event_stream.queue.Empty
            return None

        def put(self, item) -> None:
            pass

    def fake_run_coroutine_threadsafe(coro, loop):
        coro.close()
        return None

    monkeypatch.setattr(_pipeline_event_stream.queue, "Queue", FakeQueue)
    monkeypatch.setattr(
        _pipeline_event_stream.asyncio,
        "run_coroutine_threadsafe",
        fake_run_coroutine_threadsafe,
    )

    gen = _pipeline_event_stream.stream_task_events(
        loop=asyncio.new_event_loop(),
        database_url="postgresql://db",
        task_id=str(uuid.uuid4()),
        cursor=None,
    )

    assert next(gen) == ": heartbeat\n\n"
    try:
        next(gen)
    except StopIteration:
        pass
    else:
        raise AssertionError("stream_task_events deveria encerrar ao receber sentinel None")


def test_done_full_text_becomes_text_event_when_chunks_are_missing() -> None:
    msg = types.SimpleNamespace(
        done=types.SimpleNamespace(
            full_text="Resposta final", prompt_tokens=10, completion_tokens=3
        )
    )

    assert _grpc_event_handlers.final_text_fallback_event(msg, streamed_text=False) == (
        "text",
        {"content": "Resposta final"},
    )
    assert _grpc_event_handlers.final_text_fallback_event(msg, streamed_text=True) is None


def test_provider_api_error_text_chunk_becomes_error_event() -> None:
    msg = types.SimpleNamespace(
        text_chunk=types.SimpleNamespace(
            text=(
                'API Error: 429 {"error":{"message":"Provider returned error",'
                '"code":429,"metadata":{"raw":"deepseek/deepseek-v4-flash:free '
                'is temporarily rate-limited upstream","provider_name":"Crucible",'
                '"is_byok":false}},"user_id":"user_should_not_leak"}'
            )
        )
    )

    event_type, data = _grpc_event_handlers.text_chunk_event(msg)

    assert event_type == "error"
    assert "429" in data["message"]
    assert "deepseek/deepseek-v4-flash:free" in data["message"]
    assert "Crucible" in data["message"]
    assert "user_should_not_leak" not in data["message"]


def test_clean_assistant_text_removes_tool_chatter_before_final_answer() -> None:
    raw = (
        'Search repository for "1556".Open regra_nf.py.Read relevant lines.'
        "**Diagnóstico**\nO problema está na regra de CFOP."
    )

    assert _assistant_output.clean_assistant_text(raw).startswith("**Diagnóstico**")


def test_clean_assistant_text_rejects_tool_plan_without_answer() -> None:
    raw = (
        'Search repo for "ticketlog".Open venda.py.Read the relevant segment.'
        "#### Bash tool call\n```bash\nrg ticketlog\n```"
    )

    assert _assistant_output.clean_assistant_text(raw) == ""


def test_clean_assistant_text_rejects_internal_english_draft() -> None:
    raw = (
        "Likely need to adjust motivo_movto to have recolha_notas flag. "
        "Then use view to select older sales. Search send methods.Open view."
    )

    assert _assistant_output.clean_assistant_text(raw) == ""


async def test_final_message_lookup_uses_latest_user_turn_as_floor() -> None:
    conversation_id = uuid.uuid4()
    task_created = datetime(2026, 5, 20, 17, 35, 15, tzinfo=UTC)
    user_created = task_created - timedelta(seconds=1)
    message_id = uuid.uuid4()
    content = "Resposta final limpa"

    class FakeConn:
        def __init__(self) -> None:
            self.fetch_args: tuple[Any, ...] | None = None

        async def fetchrow(self, query: str, *args: Any) -> dict[str, Any]:
            return {"created_at": user_created}

        async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
            self.fetch_args = args
            return [{"id": message_id, "content": content}]

    conn = FakeConn()

    existing = await _task_final_message._find_existing_response_message(
        conn,
        conversation_id,
        content,
        {"created_at": task_created},
    )

    assert existing and existing["id"] == message_id
    assert conn.fetch_args == (conversation_id, user_created)


async def test_clean_existing_final_message_refreshes_usage_metadata() -> None:
    message_id = uuid.uuid4()
    task = {
        "model_used": "openai/gpt-oss-120b:free",
        "prompt_tokens": 100,
        "completion_tokens": 25,
        "cost_usd": Decimal("0"),
    }

    class FakeConn:
        def __init__(self) -> None:
            self.execute_args: tuple[Any, ...] | None = None

        async def execute(self, query: str, *args: Any) -> None:
            self.execute_args = args

    conn = FakeConn()

    await _task_final_message._clean_existing_message(
        conn,
        {"id": message_id, "content": "Resposta final limpa"},
        "Resposta final limpa",
        task,
    )

    assert conn.execute_args == (
        "openai/gpt-oss-120b:free",
        100,
        25,
        Decimal("0"),
        message_id,
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
