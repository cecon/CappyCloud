"""Regression tests for repository-agnostic agent context."""

from __future__ import annotations

import sys
import types
from importlib import util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
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


def test_evidence_prefetch_terms_are_domain_agnostic() -> None:
    terms = _terms_for(
        "Investigue no repo de billing por que a cobrança recorrente falha "
        "quando payment_provider_status fica pending"
    )

    assert "repo" not in [term.lower() for term in terms]
    assert "billing" in terms
    assert "payment_provider_status" in terms
