"""Extração de termos de busca para evidências automáticas."""

from __future__ import annotations

import re

from ._evidence_utils import _dedupe

_MAX_TERMS = 6
_STOP_TERMS = {
    "analise",
    "análise",
    "codigo",
    "código",
    "documentacao",
    "documentação",
    "evidencia",
    "evidência",
    "investigue",
    "mapeie",
    "mostre",
    "procure",
    "repo",
    "repositorio",
    "repositório",
    "sobre",
}


def _terms_for(message: str) -> list[str]:
    marker = "## Mensagem do utilizador"
    if marker in message:
        message = message.split(marker, 1)[1]
    raw = message.lower()
    terms: list[str] = []

    quoted = re.findall(r'"([^"]{3,60})"', message)
    terms.extend(q.strip() for q in quoted)

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
        if 4 <= len(phrase) <= 60 and phrase.lower() in raw:
            terms.append(phrase)

    for token in re.findall(r"\b\d{2,12}\b", message):
        terms.append(token)

    for token in re.findall(r"[a-zA-Z_][\w_]{3,}", message):
        if token.lower() in _STOP_TERMS:
            continue
        terms.append(token)

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
