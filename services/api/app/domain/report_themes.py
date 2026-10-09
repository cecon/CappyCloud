"""Temas do relatório de uso: regras determinísticas sobre o texto da consulta.

Cada tema tem expressões regulares aplicadas ao título e à primeira mensagem
do usuário, sem diferença de maiúsculas e acentos. A primeira regra que casar
vence; sem casamento, a consulta vai para ``outros``. Sem custo e sem LLM: o
mesmo filtro dá sempre o mesmo número.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

OTHER_THEME_KEY = "outros"
OTHER_THEME_LABEL = "Outros"
DEFAULT_PRESET = "generico"

MAX_RULES = 30
MAX_PATTERNS = 30
MAX_PATTERN_LEN = 200
MAX_LABEL_LEN = 80
_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")


class InvalidThemeRulesError(ValueError):
    """Regras de tema que não podem ser gravadas."""


@dataclass(frozen=True)
class ThemeRule:
    key: str
    label: str
    patterns: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"key": self.key, "label": self.label, "patterns": list(self.patterns)}


def normalize_text(text: str) -> str:
    """Minúsculas e sem acentos, para casar ``rejeição`` com ``rejeicao``."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def _rule(key: str, label: str, *patterns: str) -> ThemeRule:
    return ThemeRule(key=key, label=label, patterns=patterns)


PRESETS: dict[str, tuple[str, tuple[ThemeRule, ...]]] = {
    DEFAULT_PRESET: (
        "Genérico",
        (
            _rule(
                "desempenho",
                "Desempenho / lentidão",
                r"\blent(o|a|idao)\b",
                r"demor",
                r"performance",
                r"timeout",
            ),
            _rule(
                "erro-rejeicao",
                "Erro / rejeição",
                r"rejei",
                r"\berros?\b",
                r"falha",
                r"exception",
                r"\be\d{3}\b",
            ),
            _rule(
                "fiscal",
                "Fiscal / tributário",
                r"\bnf[cs]?-?e\b",
                r"\bsped\b",
                r"\bicms\b",
                r"\bpis\b",
                r"\bcofins\b",
                r"\bibs\b",
                r"\bcbs\b",
                r"tribut",
                r"\bciap\b",
                r"\bmdf-?es?\b",
                r"fiscal",
            ),
            _rule(
                "integracao",
                "Integração / API",
                r"\bapis?\b",
                r"integra",
                r"webhook",
                r"sincron",
            ),
            _rule(
                "dados",
                "Banco de dados / consultas",
                r"tabela",
                r"procedure",
                r"\bsp_",
                r"\bsql\b",
                r"consulta",
            ),
            _rule(
                "configuracao",
                "Configuração / parâmetros",
                r"configura",
                r"parametr",
                r"\bativ(ar|amos|o)\b",
                r"habilit",
                r"\bmenu\b",
                r"atalho",
            ),
            _rule(
                "arquitetura",
                "Arquitetura / visão do projeto",
                r"arquitetura",
                r"\bstacks?\b",
                r"projeto",
                r"fluxo",
                r"rotina",
            ),
            _rule(
                "documentacao",
                "Documentação / relatório técnico",
                r"documenta",
                r"confluence",
                r"linx ?share",
                r"artigo",
                r"lei do bem",
            ),
        ),
    ),
    "nfse-protheus": (
        "NFS-e (Protheus)",
        (
            _rule(
                "nfse-emissor-nacional",
                "NFS-e: Emissor / padrão nacional",
                r"emissor nacional",
                r"padrao nacional",
                r"sefin",
                r"\bdps\b",
                r"9000009",
            ),
            _rule(
                "nfse-reforma-tributaria",
                "NFS-e: Reforma tributária (IBS/CBS)",
                r"\bibs\b",
                r"\bcbs\b",
                r"ibscbs",
                r"classificacao tributaria",
                r"reforma tributaria",
                r"_rt\b",
            ),
            _rule(
                "nfse-retencoes",
                "NFS-e: Retenções e ISS",
                r"retenc",
                r"retid[oa]",
                r"\biss\b",
                r"deduc",
                r"vdedred",
            ),
            _rule(
                "nfse-schema-xml",
                "NFS-e: Schema / layout XML",
                r"schema",
                r"layout",
                r"\bxml\b",
                r"\btag\b",
                r"element",
                r"inddest",
                r"clocprestacao",
            ),
            _rule(
                "nfse-rejeicao-codigo",
                "NFS-e: Rejeição por código",
                r"rejei",
                r"\be\d{3}\b",
                r"\b\d{3,4} ?- ",
                r"falha",
                r"\berros?\b",
            ),
            _rule(
                "visao-projeto",
                "Visão geral / exploração",
                r"(sobre|explique?) (esse|este|o) projeto",
                r"arquitetura",
                r"\bstacks?\b",
            ),
        ),
    ),
}


def preset_choices() -> list[tuple[str, str]]:
    """``(chave, rótulo)`` dos modelos prontos."""
    return [(key, label) for key, (label, _rules) in PRESETS.items()]


def preset_rules(preset: str) -> tuple[ThemeRule, ...]:
    if preset not in PRESETS:
        raise InvalidThemeRulesError(f"Modelo de temas desconhecido: {preset}.")
    return PRESETS[preset][1]


def _validate_rule(raw: Any, index: int) -> ThemeRule:
    where = f"Tema {index + 1}"
    if not isinstance(raw, dict):
        raise InvalidThemeRulesError(f"{where}: esperado objeto com key, label e patterns.")
    key = str(raw.get("key") or "").strip()
    label = str(raw.get("label") or "").strip()
    patterns = raw.get("patterns")
    if not _KEY_RE.match(key):
        raise InvalidThemeRulesError(
            f"{where}: key deve ter só letras minúsculas, números e hífen (até 48)."
        )
    if key == OTHER_THEME_KEY:
        raise InvalidThemeRulesError(f"{where}: a key '{OTHER_THEME_KEY}' é reservada.")
    if not label or len(label) > MAX_LABEL_LEN:
        raise InvalidThemeRulesError(f"{where}: label deve ter de 1 a {MAX_LABEL_LEN} caracteres.")
    if not isinstance(patterns, list) or not 1 <= len(patterns) <= MAX_PATTERNS:
        raise InvalidThemeRulesError(f"{where}: patterns deve ter de 1 a {MAX_PATTERNS} itens.")
    cleaned: list[str] = []
    for pattern in patterns:
        text = str(pattern or "").strip()
        if not text or len(text) > MAX_PATTERN_LEN:
            raise InvalidThemeRulesError(
                f"{where}: cada padrão deve ter de 1 a {MAX_PATTERN_LEN} caracteres."
            )
        try:
            re.compile(normalize_text(text))
        except re.error as exc:
            raise InvalidThemeRulesError(f"{where}: padrão inválido '{text}' ({exc}).") from exc
        cleaned.append(text)
    return ThemeRule(key=key, label=label, patterns=tuple(cleaned))


def validate_theme_rules(raw: Any) -> tuple[ThemeRule, ...]:
    """Valida regras vindas do banco ou do super admin."""
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_RULES:
        raise InvalidThemeRulesError(f"Informe de 1 a {MAX_RULES} temas.")
    rules = tuple(_validate_rule(item, idx) for idx, item in enumerate(raw))
    keys = [rule.key for rule in rules]
    duplicated = sorted({key for key in keys if keys.count(key) > 1})
    if duplicated:
        raise InvalidThemeRulesError(f"Keys repetidas: {', '.join(duplicated)}.")
    return rules


def resolve_rules(preset: str | None, custom: Any) -> tuple[ThemeRule, ...]:
    """Regras próprias → modelo do workspace → modelo genérico.

    Regras gravadas que deixaram de ser válidas não derrubam o relatório:
    cai-se no modelo.
    """
    if custom:
        try:
            return validate_theme_rules(custom)
        except InvalidThemeRulesError:
            pass
    if preset in PRESETS:
        return PRESETS[preset][1]
    return PRESETS[DEFAULT_PRESET][1]


class ThemeClassifier:
    """Compila as regras uma vez e classifica muitos textos."""

    def __init__(self, rules: Sequence[ThemeRule]) -> None:
        self._rules = [
            (rule, [re.compile(normalize_text(p), re.IGNORECASE) for p in rule.patterns])
            for rule in rules
        ]

    def classify(self, text: str) -> tuple[str, str]:
        """``(key, label)`` do primeiro tema que casar, ou ``outros``."""
        normalized = normalize_text(text)
        for rule, compiled in self._rules:
            if any(regex.search(normalized) for regex in compiled):
                return rule.key, rule.label
        return OTHER_THEME_KEY, OTHER_THEME_LABEL
