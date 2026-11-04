"""Histórico da conversa no prompt do openclaude, que não guarda turnos."""

from __future__ import annotations

from tests.unit.agent_runtime_test_loader import ROOT, load_agent_module

_history = load_agent_module(
    "services.cappycloud_agent._conversation_history",
    ROOT / "services/cappycloud_agent/_conversation_history.py",
)

# Caso real (chamado 30674796): o complemento do cliente chegou sem a análise anterior.
_MESSAGES = [
    {"role": "user", "content": "Analisar a rejeição E0604 para Brasília na versão 1.01."},
    {"role": "assistant", "content": "**ORIENTAÇÃO** A DPS saiu com pAliq e regEspTrib 6."},
    {"role": "user", "content": "Segundo cliente, o regEspTrib = 6 é do segmento jurídico."},
]


def test_tira_a_pergunta_atual_e_mantem_a_ordem() -> None:
    section = _history.render_conversation_history(_MESSAGES)

    assert section.startswith("## Histórico desta conversa")
    assert "segmento jurídico" not in section
    assert section.index("Analisar a rejeição") < section.index("**ORIENTAÇÃO**")
    assert "**Usuário:**" in section and "**Assistente:**" in section


def test_primeira_mensagem_nao_tem_historico() -> None:
    assert _history.render_conversation_history(_MESSAGES[:1]) == ""
    assert _history.render_conversation_history(None) == ""
    assert _history.inject_conversation_history("prompt", []) == "prompt"


def test_corta_pelo_tamanho_mantendo_os_turnos_mais_recentes() -> None:
    messages = [
        {"role": "user", "content": "primeira " + "a" * 500},
        {"role": "assistant", "content": "recente " + "b" * 500},
        {"role": "user", "content": "atual"},
    ]
    section = _history.render_conversation_history(messages, max_chars=600)

    assert "recente" in section
    assert "primeira" not in section
    assert "1 mensagens mais antigas foram omitidas" in section


def test_mensagem_longa_e_cortada_mas_entra() -> None:
    messages = [
        {"role": "assistant", "content": "x" * 50},
        {"role": "user", "content": "atual"},
    ]
    section = _history.render_conversation_history(messages, max_message_chars=10)

    assert "x" * 10 + "\n[…trecho cortado]" in section


def test_historico_entra_antes_da_mensagem_do_usuario() -> None:
    prompt = "## Worktree\n\n---\n\n## Mensagem do utilizador\n\nSegundo cliente..."
    injected = _history.inject_conversation_history(prompt, _MESSAGES)

    assert injected.index("## Worktree") < injected.index("## Histórico desta conversa")
    assert injected.index("## Histórico desta conversa") < injected.index(
        "## Mensagem do utilizador"
    )
    assert injected.endswith("Segundo cliente...")
