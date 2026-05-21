"""Extração de termos de busca para evidências automáticas."""

from __future__ import annotations

import re

from ._evidence_utils import _dedupe

_MAX_TERMS = 6
_STOP_TERMS = {
    "agora",
    "analise",
    "análise",
    "antes",
    "apos",
    "após",
    "aquele",
    "aquela",
    "aquilo",
    "assim",
    "cliente",
    "clientes",
    "codigo",
    "código",
    "como",
    "com",
    "corrigimos",
    "corrigir",
    "depois",
    "documentacao",
    "documentação",
    "eles",
    "essa",
    "esse",
    "esta",
    "está",
    "estavam",
    "evidencia",
    "evidência",
    "fazer",
    "foram",
    "para",
    "pela",
    "pelo",
    "investigue",
    "isso",
    "mapeie",
    "mostre",
    "nao",
    "não",
    "nota",
    "notas",
    "onde",
    "procure",
    "quando",
    "qual",
    "quais",
    "que",
    "repo",
    "repositorio",
    "repositório",
    "sem",
    "sobre",
    "temos",
    "usando",
    "usar",
    "voces",
    "vocês",
}
_CONNECTOR_TERMS = {"de", "da", "das", "do", "dos", "e", "em", "no", "nos"}
_PRODUCT_HINTS = {"autosystem", "linx", "seller", "smartpos", "ticketlog"}


def _word_tokens(message: str) -> list[str]:
    return re.findall(r"[a-zA-ZÀ-ÿ0-9_][\wÀ-ÿ_]*", message)


def _is_signal_token(token: str) -> bool:
    lowered = token.lower()
    return len(lowered) >= 3 and lowered not in _STOP_TERMS and lowered not in _CONNECTOR_TERMS


def _is_product_token(token: str) -> bool:
    lowered = token.lower()
    if lowered in _PRODUCT_HINTS:
        return True
    return (
        any(ch.isupper() for ch in token[1:])
        or token.isupper()
        or "_" in token
        or "-" in token
    )


def _terms_for(message: str) -> list[str]:
    marker = "## Mensagem do utilizador"
    if marker in message:
        message = message.split(marker, 1)[1]
    raw = message.lower()
    terms: list[str] = []

    quoted = re.findall(r'"([^"]{3,60})"', message)
    terms.extend(q.strip() for q in quoted)

    words = _word_tokens(message)
    signal_words = [word for word in words if _is_signal_token(word)]
    product_words = [word for word in signal_words if _is_product_token(word)]

    lowered_signals = {word.lower() for word in signal_words}
    if "recolha" in lowered_signals and "ticketlog" in lowered_signals:
        product = next(
            (word for word in product_words if word.lower() == "ticketlog"),
            "TicketLog",
        )
        if "notas" in raw:
            terms.append(f"{product} recolha notas")
            terms.append(f"recolha notas {product}")
        else:
            terms.append(f"{product} recolha")

    terms.extend(product_words)
    terms.extend(word for word in signal_words if "_" in word)
    terms.extend(signal_words[:3])

    for index in range(max(0, len(signal_words) - 2)):
        terms.append(" ".join(signal_words[index : index + 3]))
    for index in range(max(0, len(signal_words) - 1)):
        terms.append(" ".join(signal_words[index : index + 2]))

    for token in re.findall(r"[a-zA-Z_][\w_]{3,}", message):
        token_lower = token.lower()
        if "_" in token and token_lower not in _STOP_TERMS:
            terms.append(token)

    phrase_candidates = re.findall(
        r"[a-zA-ZÀ-ÿ0-9_][\wÀ-ÿ_]*(?:[\s\-/]+[a-zA-ZÀ-ÿ0-9_][\wÀ-ÿ_]*){1,3}",
        message,
    )
    for phrase in phrase_candidates:
        phrase = " ".join(phrase.split())
        phrase_tokens = [
            token for token in _word_tokens(phrase) if token.lower() not in _CONNECTOR_TERMS
        ]
        signal_count = sum(1 for token in phrase_tokens if _is_signal_token(token))
        if 4 <= len(phrase) <= 60 and phrase.lower() in raw and signal_count >= 2:
            terms.append(phrase)

    for token in re.findall(r"\b\d{2,12}\b", message):
        terms.append(token)

    terms.extend(signal_words)

    return _dedupe(terms)[:_MAX_TERMS]


def _parameter_numbers(message: str) -> list[str]:
    marker = "## Mensagem do utilizador"
    if marker in message:
        message = message.split(marker, 1)[1]
    lower = message.lower()
    if not re.search(
        r"\b(?:par[aâ]metro|parametro|param|parametros|par[aâ]metros)\b", lower
    ):
        return []
    return _dedupe(re.findall(r"\b\d{1,12}\b", message))
