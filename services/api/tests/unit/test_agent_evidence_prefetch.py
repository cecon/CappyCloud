"""Regression tests for automatic evidence prefetch."""

from __future__ import annotations

import sys
import types
from importlib import util
from pathlib import Path


def _find_repo_root() -> Path:
    current = Path(__file__).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "services" / "cappycloud_agent").is_dir():
            return candidate
    raise RuntimeError("Não encontrei 'services/cappycloud_agent' no worktree.")


ROOT = _find_repo_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_module(name: str, path: Path) -> types.ModuleType:
    spec = util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_agent_pkg = types.ModuleType("services.cappycloud_agent")
_agent_pkg.__path__ = [str(ROOT / "services/cappycloud_agent")]  # type: ignore[attr-defined]
sys.modules.setdefault("services.cappycloud_agent", _agent_pkg)
_agent_context = types.ModuleType("services.cappycloud_agent._agent_context")
_agent_context.inject_section_before_user_message = lambda prompt, section: f"{section}\n{prompt}"
sys.modules["services.cappycloud_agent._agent_context"] = _agent_context
_evidence_prefetch = _load_module(
    "services.cappycloud_agent._evidence_prefetch",
    ROOT / "services/cappycloud_agent/_evidence_prefetch.py",
)

_terms_for = _evidence_prefetch._terms_for
_confluence_sources = _evidence_prefetch._confluence_sources
_parameter_lookup_guard = _evidence_prefetch._parameter_lookup_guard
_parameter_numbers = _evidence_prefetch._parameter_numbers
_parameter_dirs_from_files = _evidence_prefetch._parameter_dirs_from_files
_active_parameter_dirs = _evidence_prefetch._active_parameter_dirs
_parameter_doc_result_lines = _evidence_prefetch._parameter_doc_result_lines
_render_section = _evidence_prefetch._render_section
_DocHit = _evidence_prefetch._DocHit
_DocSearchAttempt = _evidence_prefetch._DocSearchAttempt
_ConfluenceSource = _evidence_prefetch._ConfluenceSource


def test_evidence_prefetch_terms_are_domain_agnostic() -> None:
    terms = _terms_for(
        "Investigue no repo de billing por que a cobrança recorrente falha "
        "quando payment_provider_status fica pending"
    )

    assert "repo" not in [term.lower() for term in terms]
    assert "billing" in terms
    assert "payment_provider_status" in terms


def test_evidence_prefetch_terms_include_numeric_parameters() -> None:
    terms = _terms_for("o que o parametro 630 faz?")

    assert "630" in terms


def test_parameter_numbers_only_trigger_for_parameter_questions() -> None:
    assert _parameter_numbers("o que o parâmetro 630 faz?") == ["630"]
    assert _parameter_numbers("procure NCM 01063000") == []


def test_parameter_lookup_guard_points_to_generic_parameter_paths() -> None:
    section = _parameter_lookup_guard(
        "o que o parametro 630 faz?",
        [{"slug": "react", "alias": "React", "worktree_path": "/repos/sessions/abc/React"}],
        "/repos/sessions/abc",
    )

    assert "/repos/sessions/abc/React/Parametros" in section
    assert "/repos/sessions/abc/React/parameters" in section
    assert "localizar diretórios `*/Parametros` ou `*/parameters`" in section
    assert "não faça busca ampla no repositório" in section
    assert "descoberta de diretórios" in section
    assert "Confluence sem resultados" in section
    assert "NCM" in section
    assert "GUID" in section


def test_parameter_dirs_discover_nested_parametros() -> None:
    directories = _parameter_dirs_from_files(
        "React",
        "/repos/sessions/abc/React",
        [
            "packages/react/Parametros/Parametro630.ts",
            "packages/react/Parametros/Outro.ts",
            "packages/react/src/index.ts",
        ],
    )
    active = _active_parameter_dirs(directories)

    assert len(active) == 1
    assert active[0].path == "/repos/sessions/abc/React/packages/react/Parametros"
    assert active[0].preferred is False


def test_parameter_dirs_accept_english_parameters() -> None:
    directories = _parameter_dirs_from_files(
        "React",
        "/repos/sessions/abc/React",
        [
            "packages/scheduler/parameters/config.ts",
            "packages/scheduler/parameters/groups.ts",
        ],
    )
    active = _active_parameter_dirs(directories)
    section = _parameter_lookup_guard(
        "o que o parametro 630 faz?",
        [{"slug": "react", "alias": "React", "worktree_path": "/repos/sessions/abc/React"}],
        "/repos/sessions/abc",
        active,
    )

    assert len(active) == 1
    assert active[0].path.endswith("/packages/scheduler/parameters")
    assert "packages/scheduler/parameters" in section
    assert "busca ampla por `630` na raiz do repo" in section


def test_parameter_guard_carries_confirmed_confluence_no_result() -> None:
    attempts = [
        _DocSearchAttempt(
            "630",
            _ConfluenceSource("https://docs.example.com/wiki", "Frontend", ("react", "react-dom")),
        )
    ]
    section = _parameter_lookup_guard(
        "o que o parametro 630 faz?",
        [{"slug": "react", "alias": "React", "worktree_path": "/repos/sessions/abc/React"}],
        "/repos/sessions/abc",
        [],
        [],
        attempts,
    )

    assert "Documentação externa já consultada automaticamente" in section
    assert "Confluence para `630`: sem resultados retornados" in section
    assert "space `Frontend`" in section
    assert "não escreva 'caso o Confluence não traga resultados'" in section


def test_parameter_doc_result_lines_ignore_successful_docs() -> None:
    assert _parameter_doc_result_lines([_DocHit("630", "Titulo", "https://x", "Resumo")], []) == []


def test_evidence_prefetch_carries_space_and_labels() -> None:
    sources = _confluence_sources(
        [
            {
                "confluence_url": "https://docs.example.com/wiki",
                "confluence_space": "Frontend",
                "confluence_labels": ["react", "react-dom"],
            }
        ]
    )

    assert len(sources) == 1
    assert sources[0].base_url == "https://docs.example.com/wiki"
    assert sources[0].space == "Frontend"
    assert sources[0].labels == ("react", "react-dom")


def test_evidence_prefetch_renders_empty_confluence_attempts() -> None:
    section = _render_section(
        [],
        [],
        [
            _DocSearchAttempt(
                "630",
                _ConfluenceSource(
                    "https://docs.example.com/wiki", "Frontend", ("react", "react-dom")
                ),
            )
        ],
    )

    assert "Documentação consultada automaticamente sem resultados" in section
    assert "`630` → Confluence sem resultados retornados" in section
    assert "já foram executadas pelo CappyCloud" in section
    assert "Resultado documental já verificado" in section
    assert "não como hipótese" in section
    assert "não diga apenas que o utilizador deve consultar documentação oficial" in section
    assert "space `Frontend`" in section
    assert "labels `react`, `react-dom`" in section
