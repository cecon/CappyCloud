"""Testes mutation-resistant para ``render_session_tools``.

O módulo alvo (``cappycloud_agent._agent_prompt_sections``) é self-contained
(só depende de stdlib), mas pertence a um pacote cujo ``__init__.py``
importa Pipeline + dependências gRPC que não existem no ambiente de teste
da API. Por isso carregamos o arquivo via ``importlib`` em vez de import
normal — registrando-o em ``sys.modules`` com um nome estável para que
mutmut consiga rastrear cobertura.

Ver docs/AGENT_RULES.md §6.1.
"""

from __future__ import annotations

import sys
from importlib import util
from pathlib import Path


def _load_target_module():
    here = Path(__file__).resolve()
    target: Path | None = None
    for candidate in [here, *here.parents]:
        maybe = candidate / "services" / "cappycloud_agent" / "_agent_prompt_sections.py"
        if maybe.is_file():
            target = maybe
            break
    if target is None:
        raise RuntimeError("_agent_prompt_sections.py não encontrado a partir de " + str(here))

    module_name = "cappycloud_agent_prompt_sections_under_test"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = util.spec_from_file_location(module_name, target)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_target = _load_target_module()
render_session_tools = _target.render_session_tools

SANDBOX_URL = "http://sandbox:8080"


# ── confluence_url propagation ────────────────────────────────────────────


def test_render_session_tools_emits_no_confluence_block_when_no_repo_has_url() -> None:
    rendered = render_session_tools(SANDBOX_URL, [{"slug": "api"}])
    assert "/confluence/search" not in rendered
    assert "não consulte `/confluence/*`" in rendered.lower()


def test_render_session_tools_url_encodes_base_url() -> None:
    rendered = render_session_tools(
        SANDBOX_URL,
        [{"slug": "api", "confluence_url": "https://docs.example.com/wiki"}],
    )
    assert "base_url=https%3A%2F%2Fdocs.example.com%2Fwiki" in rendered
    # URL sem encode não pode vazar (caracteres `:` e `/` quebrariam a query)
    assert "base_url=https://docs.example.com/wiki" not in rendered


def test_render_session_tools_uses_alias_when_present() -> None:
    rendered = render_session_tools(
        SANDBOX_URL,
        [
            {
                "slug": "api",
                "alias": "api-main",
                "confluence_url": "https://x.example/wiki",
            }
        ],
    )
    assert "**api-main**" in rendered
    assert "**api**:" not in rendered


def test_render_session_tools_falls_back_to_slug_when_no_alias() -> None:
    rendered = render_session_tools(
        SANDBOX_URL,
        [{"slug": "api", "confluence_url": "https://x.example/wiki"}],
    )
    assert "**api**" in rendered


# ── confluence_space propagation ──────────────────────────────────────────


def test_render_session_tools_includes_space_param_when_space_set() -> None:
    rendered = render_session_tools(
        SANDBOX_URL,
        [
            {
                "slug": "api",
                "confluence_url": "https://x.example/wiki",
                "confluence_space": "FRONTEND",
            }
        ],
    )
    # &space= deve aparecer entre base_url e q
    assert "&space=FRONTEND&q=" in rendered


def test_render_session_tools_includes_space_label_when_space_set() -> None:
    rendered = render_session_tools(
        SANDBOX_URL,
        [
            {
                "slug": "api",
                "confluence_url": "https://x.example/wiki",
                "confluence_space": "FRONTEND",
            }
        ],
    )
    assert "(space `FRONTEND`)" in rendered


def test_render_session_tools_includes_labels_param_when_labels_set() -> None:
    rendered = render_session_tools(
        SANDBOX_URL,
        [
            {
                "slug": "react",
                "confluence_url": "https://x.example/wiki",
                "confluence_space": "Frontend",
                "confluence_labels": ["react", "react-dom"],
            }
        ],
    )
    assert "&space=Frontend&labels=react,react-dom&q=" in rendered
    assert "labels `react`, `react-dom`" in rendered
    assert "Nos perfis rápido e médio, consulte Confluence quando" in rendered


def test_render_session_tools_url_encodes_labels_with_special_chars() -> None:
    rendered = render_session_tools(
        SANDBOX_URL,
        [
            {
                "slug": "api",
                "confluence_url": "https://x.example/wiki",
                "confluence_labels": ["react dom", "react&native"],
            }
        ],
    )
    assert "&labels=react%20dom,react%26native&q=" in rendered
    assert "&labels=react dom" not in rendered


def test_render_session_tools_omits_space_when_space_missing() -> None:
    rendered = render_session_tools(
        SANDBOX_URL,
        [{"slug": "api", "confluence_url": "https://x.example/wiki"}],
    )
    assert "&space=" not in rendered
    assert "(space `" not in rendered


def test_render_session_tools_omits_space_when_space_empty_string() -> None:
    rendered = render_session_tools(
        SANDBOX_URL,
        [
            {
                "slug": "api",
                "confluence_url": "https://x.example/wiki",
                "confluence_space": "",
            }
        ],
    )
    assert "&space=" not in rendered
    assert "(space `" not in rendered


def test_render_session_tools_omits_space_when_whitespace_only() -> None:
    """Mutação que troque `.strip()` por nada deve ser detectada."""
    rendered = render_session_tools(
        SANDBOX_URL,
        [
            {
                "slug": "api",
                "confluence_url": "https://x.example/wiki",
                "confluence_space": "   \t  ",
            }
        ],
    )
    assert "&space=" not in rendered


def test_render_session_tools_url_encodes_space_with_spaces() -> None:
    rendered = render_session_tools(
        SANDBOX_URL,
        [
            {
                "slug": "api",
                "confluence_url": "https://x.example/wiki",
                "confluence_space": "MY SPACE",
            }
        ],
    )
    assert "&space=MY%20SPACE&q=" in rendered
    # Não vazar versão não-encodada
    assert "&space=MY SPACE" not in rendered


def test_render_session_tools_url_encodes_space_with_special_chars() -> None:
    rendered = render_session_tools(
        SANDBOX_URL,
        [
            {
                "slug": "api",
                "confluence_url": "https://x.example/wiki",
                "confluence_space": "A&B",
            }
        ],
    )
    assert "&space=A%26B&q=" in rendered
    # `A&B` cru quebraria a query string (& vira separador)
    assert "&space=A&B&q=" not in rendered


def test_render_session_tools_isolates_space_per_repo() -> None:
    """Multi-repo: o &space= só aparece na linha do repo que tem space."""
    rendered = render_session_tools(
        SANDBOX_URL,
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
    assert "&space=" not in line_b


def test_render_session_tools_emits_isolation_guidance_only_when_any_space() -> None:
    """A guidance sobre 'restrita ao produto correto' depende de ALGUM repo ter space."""
    no_space = render_session_tools(
        SANDBOX_URL,
        [{"slug": "a", "confluence_url": "https://x.example/wiki"}],
    )
    assert "restrita ao produto correto" not in no_space

    one_space = render_session_tools(
        SANDBOX_URL,
        [
            {"slug": "a", "confluence_url": "https://x.example/wiki"},
            {
                "slug": "b",
                "confluence_url": "https://y.example/wiki",
                "confluence_space": "B",
            },
        ],
    )
    assert "restrita ao produto correto" in one_space
