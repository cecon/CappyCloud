"""Skills dos repositórios no prompt do agente: completas quando cabem, senão índice."""

from __future__ import annotations

from .agent_runtime_test_loader import (
    agent_prompt_sections as _agent_prompt_sections,
)


def test_repo_skills_are_an_index_when_over_the_inline_limit() -> None:
    section = _agent_prompt_sections.render_repo_skills(
        [{"title": "Fiscal", "summary": "Regras fiscais", "content": "conteúdo longo"}],
        inline_max_chars=5,
    )

    assert "- **Fiscal** — Regras fiscais" in section
    assert "`/skills/search`" in section
    assert "conteúdo longo" not in section
    assert "skills globais" not in section


def test_small_repo_skills_go_in_full() -> None:
    """Caso real: o Claude Opus no openclaude não buscava as skills de NFS-e."""
    section = _agent_prompt_sections.render_repo_skills(
        [
            {"title": "1. Regras", "summary": "resumo", "content": "Valide o TSS0013."},
            {"title": "2. Resposta", "summary": "resumo", "content": "Responda em três blocos."},
        ],
        inline_max_chars=30_000,
    )

    assert "### 1. Regras\n\nValide o TSS0013." in section
    assert "Responda em três blocos." in section
    assert "não é preciso buscá-las" in section
    assert "`/skills/search`" not in section


def test_skill_without_content_keeps_the_index() -> None:
    section = _agent_prompt_sections.render_repo_skills(
        [{"title": "Fiscal", "summary": "Regras fiscais", "content": ""}],
        inline_max_chars=30_000,
    )

    assert "- **Fiscal** — Regras fiscais" in section
    assert "`/skills/search`" in section
