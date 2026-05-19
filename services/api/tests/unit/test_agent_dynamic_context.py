"""Regression tests for repository-agnostic agent context."""

from __future__ import annotations

import sys
import types
from importlib import util
from pathlib import Path


def _find_repo_root() -> Path:
    """Sobe a árvore até achar ``services/cappycloud_agent``.

    Mutmut copia o código para um sandbox próprio antes de rodar o pytest,
    então não dá pra confiar em ``parents[N]`` ou ``Path.cwd()``.
    """
    current = Path(__file__).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "services" / "cappycloud_agent").is_dir():
            return candidate
    raise RuntimeError(
        "Não encontrei 'services/cappycloud_agent' subindo a partir de "
        f"{current}. Estrutura do worktree inesperada."
    )


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


_prompt_sections = _load_module(
    "agent_prompt_sections_for_test",
    ROOT / "services/cappycloud_agent/_agent_prompt_sections.py",
)
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

render_response_rules = _prompt_sections.render_response_rules
render_session_tools = _prompt_sections.render_session_tools
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


def test_agent_prompt_sections_do_not_embed_product_specific_rules() -> None:
    text = "\n".join(
        [
            render_session_tools("http://sandbox:8080"),
            render_response_rules(),
        ]
    ).lower()

    assert "produto específico" not in text
    assert "regra cliente" not in text
    assert "documentação externa" in text


def test_session_tools_only_enable_confluence_for_configured_repos() -> None:
    without_docs = render_session_tools("http://sandbox:8080", [{"slug": "api"}])
    assert "não consulte `/confluence/*`" in without_docs.lower()
    assert "/confluence/search?base_url=" not in without_docs

    with_docs = render_session_tools(
        "http://sandbox:8080",
        [{"slug": "api", "confluence_url": "https://docs.example.com/wiki"}],
    )
    assert "/confluence/search?base_url=https%3A%2F%2Fdocs.example.com%2Fwiki" in with_docs


# --- confluence_space propagation -----------------------------------------
#
# Testes escritos para sobreviver a mutation testing
# (ver docs/AGENT_RULES.md §6.1): asserts pontuais, casos de borda,
# ambos os ramos das condicionais.


def test_session_tools_includes_space_filter_when_repo_has_space() -> None:
    """Quando space está configurado: URL contém &space=<key> e label visual."""
    rendered = render_session_tools(
        "http://sandbox:8080",
        [
            {
                "slug": "api",
                "alias": "api",
                "confluence_url": "https://docs.example.com/wiki",
                "confluence_space": "FRONTEND",
            }
        ],
    )
    assert "base_url=https%3A%2F%2Fdocs.example.com%2Fwiki&space=FRONTEND&q=" in rendered
    assert "(space `FRONTEND`)" in rendered
    assert "restrita ao produto correto" in rendered


def test_session_tools_includes_label_filter_when_repo_has_labels() -> None:
    rendered = render_session_tools(
        "http://sandbox:8080",
        [
            {
                "slug": "react",
                "alias": "React",
                "confluence_url": "https://docs.example.com/wiki",
                "confluence_space": "Frontend",
                "confluence_labels": ["react", "react-dom"],
            }
        ],
    )
    assert "&space=Frontend&labels=react,react-dom&q=" in rendered
    assert "labels `react`, `react-dom`" in rendered
    assert "rótulos são parte do escopo documental" in rendered


def test_session_tools_omits_space_when_repo_has_no_space() -> None:
    """URL sem space: NÃO emite &space= e NÃO emite label."""
    rendered = render_session_tools(
        "http://sandbox:8080",
        [
            {
                "slug": "api",
                "alias": "api",
                "confluence_url": "https://docs.example.com/wiki",
            }
        ],
    )
    assert "&space=" not in rendered
    assert "(space `" not in rendered
    assert "restrita ao produto correto" not in rendered


def test_session_tools_treats_whitespace_space_as_empty() -> None:
    """Space contendo apenas whitespace é equivalente a não configurado."""
    rendered = render_session_tools(
        "http://sandbox:8080",
        [
            {
                "slug": "api",
                "confluence_url": "https://docs.example.com/wiki",
                "confluence_space": "   ",
            }
        ],
    )
    assert "&space=" not in rendered
    assert "(space `" not in rendered


def test_session_tools_url_encodes_space_with_special_chars() -> None:
    """Space com caractere especial precisa ser url-encoded para não quebrar a query."""
    rendered = render_session_tools(
        "http://sandbox:8080",
        [
            {
                "slug": "api",
                "confluence_url": "https://docs.example.com/wiki",
                "confluence_space": "MY SPACE",
            }
        ],
    )
    assert "&space=MY%20SPACE&q=" in rendered
    assert "&space=MY SPACE" not in rendered


def test_session_tools_emits_per_repo_space_isolation() -> None:
    """Em sessão multi-repo, cada repo tem sua linha — space não vaza pro outro."""
    rendered = render_session_tools(
        "http://sandbox:8080",
        [
            {
                "slug": "a",
                "alias": "a",
                "confluence_url": "https://x.example/wiki",
                "confluence_space": "A_SPACE",
            },
            {
                "slug": "b",
                "alias": "b",
                "confluence_url": "https://y.example/wiki",
            },
        ],
    )
    line_a = next(line for line in rendered.splitlines() if "**a**" in line)
    line_b = next(line for line in rendered.splitlines() if "**b**" in line)
    assert "&space=A_SPACE&q=" in line_a
    assert "(space `A_SPACE`)" in line_a
    assert "&space=" not in line_b
    assert "(space `" not in line_b


def test_session_tools_emits_guidance_only_when_any_space_configured() -> None:
    """A frase 'restrita ao produto correto' só aparece se algum repo tiver space."""
    no_space_text = render_session_tools(
        "http://sandbox:8080",
        [{"slug": "a", "confluence_url": "https://x.example/wiki"}],
    )
    assert "restrita ao produto correto" not in no_space_text

    with_space_text = render_session_tools(
        "http://sandbox:8080",
        [
            {"slug": "a", "confluence_url": "https://x.example/wiki"},
            {"slug": "b", "confluence_url": "https://y.example/wiki", "confluence_space": "B"},
        ],
    )
    assert "restrita ao produto correto" in with_space_text
