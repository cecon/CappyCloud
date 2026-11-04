"""Histórico da conversa para o runtime openclaude.

O openclaude não guarda nada entre turnos (o patch do gRPC zera o histórico a
cada pedido): sem este bloco, a segunda mensagem chega ao modelo sem a análise
nem os dados da primeira. O Claude CLI não precisa dele, retoma a sessão pelo
``resume``.
"""

from __future__ import annotations

import os

_MAX_CHARS = int(os.getenv("CONVERSATION_HISTORY_MAX_CHARS", "40000"))
_MAX_MESSAGE_CHARS = int(os.getenv("CONVERSATION_HISTORY_MAX_MESSAGE_CHARS", "8000"))

_ROLE_LABELS = {"user": "Usuário", "assistant": "Assistente"}


def previous_turns(messages: list[dict] | None) -> list[dict]:
    """Mensagens anteriores ao turno atual: tira a pergunta que acabou de chegar."""
    turns = [
        m
        for m in messages or []
        if m.get("role") in _ROLE_LABELS and str(m.get("content") or "").strip()
    ]
    if turns and turns[-1]["role"] == "user":
        turns = turns[:-1]
    return turns


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n[…trecho cortado]"


def render_conversation_history(
    messages: list[dict] | None,
    max_chars: int = _MAX_CHARS,
    max_message_chars: int = _MAX_MESSAGE_CHARS,
) -> str:
    """Bloco com os turnos anteriores, dos mais recentes para trás até ``max_chars``."""
    turns = previous_turns(messages)
    if not turns or max_chars <= 0:
        return ""
    blocks: list[str] = []
    used = 0
    for message in reversed(turns):
        content = _clip(str(message["content"]).strip(), max_message_chars)
        block = f"**{_ROLE_LABELS[message['role']]}:**\n{content}"
        if blocks and used + len(block) > max_chars:
            break
        blocks.append(block)
        used += len(block)
    omitted = len(turns) - len(blocks)
    header = [
        "## Histórico desta conversa",
        "Turnos anteriores desta mesma conversa, do mais antigo para o mais recente. "
        "A mensagem atual do usuário continua o que está aqui: use as análises, os "
        "dados e as conclusões anteriores em vez de pedir de novo. Anexos de turnos "
        "anteriores não são reenviados; o que foi extraído deles está nas respostas.",
    ]
    if omitted:
        header.append(f"({omitted} mensagens mais antigas foram omitidas por tamanho.)")
    return "\n\n".join(header + list(reversed(blocks)))


def inject_conversation_history(prompt: str, messages: list[dict] | None) -> str:
    """Põe o histórico logo antes da mensagem do usuário (ou no topo, sem o marcador)."""
    section = render_conversation_history(messages)
    if not section:
        return prompt
    marker = "## Mensagem do utilizador"
    if marker not in prompt:
        return f"{section}\n\n---\n\n{prompt}"
    return prompt.replace(marker, f"{section}\n\n---\n\n{marker}", 1)
