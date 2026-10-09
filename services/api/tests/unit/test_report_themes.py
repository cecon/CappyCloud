"""Temas do relatório: classificação determinística e validação das regras."""

from __future__ import annotations

import pytest
from app.domain.report_themes import (
    DEFAULT_PRESET,
    MAX_RULES,
    OTHER_THEME_KEY,
    PRESETS,
    InvalidThemeRulesError,
    ThemeClassifier,
    normalize_text,
    preset_choices,
    preset_rules,
    resolve_rules,
    validate_theme_rules,
)

NFSE = ThemeClassifier(preset_rules("nfse-protheus"))
GENERIC = ThemeClassifier(preset_rules(DEFAULT_PRESET))

# Títulos / começo da primeira mensagem reais do proteus (prod, 2026-10-09).
PROTEUS_SAMPLES = [
    (
        "Ao realizar a transmissão de uma NFSE para a prefeitura de SP, ocorre a falha de "
        "schema abaixo: Element '{http://www.prefeitura.sp.gov.br/nfe}indDest'",
        "nfse-schema-xml",
    ),
    (
        "1001 - XML não compatível com Schema.The element 'RPS' has invalid child element "
        "'cLocPrestacao'",
        "nfse-schema-xml",
    ),
    (
        "Cenário 03 - Dificil\nCliente nos acionou informando que a tag indDest estava sendo "
        "montada incorretamente",
        "nfse-schema-xml",
    ),
    (
        "Rejeição da Prefeitura de SP: 651 (Para o Codigo de Classificação Tributaria informado "
        "a localidade de incidência do IBS deve ser um endereço nacional.)",
        "nfse-reforma-tributaria",
    ),
    (
        'Análise a rejeição "E370 - Não é permitido o uso de outras retenções no município" '
        "para Jundiai/SP com base no xml unico",
        "nfse-retencoes",
    ),
    (
        "Analisar a rejeição E160 - Arquivo em desacordo com o XML na versão 1.01 para Goiania",
        "nfse-schema-xml",
    ),
    (
        "Analisar a prefeitura de Aracaju na versão 2.02_RT <codigo>E160</codigo> The element "
        "'IBSCBS'",
        "nfse-reforma-tributaria",
    ),
    (
        "Analisar a rejeição para a prefeitura de Petropolis que é aderente ao emissor nacional",
        "nfse-emissor-nacional",
    ),
    (
        "Analisar as rejeições na transmissão via emissor nacional na versão 1.01 onde cod_mun "
        "= 9000009",
        "nfse-emissor-nacional",
    ),
    (
        "Validar o motivo da rejeição para a prefeitura de Salvador na versão de layout 1.00",
        "nfse-schema-xml",
    ),
    (
        "Avalie o real motivo das rejeições para Mogi das Cruzes na versão 1.01",
        "nfse-rejeicao-codigo",
    ),
    (
        "Na emissão de NFS-e pelo padrão nacional (DPS / Sefin Nacional), o Protheus manda o "
        "repasse a terceiros",
        "nfse-emissor-nacional",
    ),
    ("me fale sobre esse projeto", "visao-projeto"),
    ("ola", OTHER_THEME_KEY),
    ("Analise sem o PDF mesmo", OTHER_THEME_KEY),
]


@pytest.mark.parametrize(("text", "expected"), PROTEUS_SAMPLES)
def test_nfse_preset_classifies_real_proteus_questions(text: str, expected: str) -> None:
    assert NFSE.classify(text)[0] == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "No cadastro de itens o sistema está muito lento, levando mais de 10 minutos",
            "desempenho",
        ),
        ("o Sped Fiscal gera os registros 1300 em períodos sem venda?", "fiscal"),
        ("vTotIBSMonoItem esta tag é informada no XML de venda da NFe?", "fiscal"),
        ("como funcionam as apis de envio de saldos de estoques para o hyperlocal", "integracao"),
        ("Quais rotinas chamam a sp_validar_dta_vencimento?", "dados"),
        ("como ativar o qrlinx no pdv?", "configuracao"),
        ("quais as stacks deste projeto", "arquitetura"),
        ("existe documentação no linxshare referente a leitura de placa?", "documentacao"),
        ("ola", OTHER_THEME_KEY),
    ],
)
def test_generic_preset_classifies_other_workspaces(text: str, expected: str) -> None:
    assert GENERIC.classify(text)[0] == expected


def test_classification_ignores_case_and_accents() -> None:
    assert NFSE.classify("RETENÇÕES no município")[0] == "nfse-retencoes"
    assert NFSE.classify("retencoes no municipio")[0] == "nfse-retencoes"
    assert normalize_text("Rejeição ÀÉÎõü") == "rejeicao aeiou"


def test_first_matching_rule_wins() -> None:
    rules = validate_theme_rules(
        [
            {"key": "a", "label": "A", "patterns": ["xml"]},
            {"key": "b", "label": "B", "patterns": ["xml", "nota"]},
        ]
    )
    classifier = ThemeClassifier(rules)
    assert classifier.classify("xml da nota") == ("a", "A")
    assert classifier.classify("nota") == ("b", "B")
    assert classifier.classify("nada") == (OTHER_THEME_KEY, "Outros")


def test_presets_have_unique_keys_and_valid_patterns() -> None:
    for _label, rules in PRESETS.values():
        validate_theme_rules([rule.as_dict() for rule in rules])
    assert [key for key, _ in preset_choices()] == ["generico", "nfse-protheus"]


def test_unknown_preset_is_rejected() -> None:
    with pytest.raises(InvalidThemeRulesError, match="desconhecido"):
        preset_rules("nao-existe")


def test_resolve_rules_prefers_custom_then_preset_then_generic() -> None:
    custom = [{"key": "meu", "label": "Meu", "patterns": ["x"]}]
    assert [r.key for r in resolve_rules("nfse-protheus", custom)] == ["meu"]
    assert resolve_rules("nfse-protheus", None) == preset_rules("nfse-protheus")
    assert resolve_rules(None, None) == preset_rules(DEFAULT_PRESET)
    assert resolve_rules("sumiu", []) == preset_rules(DEFAULT_PRESET)
    # Regras gravadas que ficaram inválidas não derrubam o relatório.
    broken = [{"key": "x", "label": "X", "patterns": ["("]}]
    assert resolve_rules("nfse-protheus", broken) == preset_rules("nfse-protheus")


def _rule(**overrides: object) -> dict[str, object]:
    return {"key": "tema", "label": "Tema", "patterns": ["abc"], **overrides}


@pytest.mark.parametrize(
    ("rules", "message"),
    [
        ([], "de 1 a 30 temas"),
        ("nao-lista", "de 1 a 30 temas"),
        ([_rule() for _ in range(MAX_RULES + 1)], "de 1 a 30 temas"),
        (["texto"], "esperado objeto"),
        ([_rule(key="Com Espaco")], "key deve ter"),
        ([_rule(key="")], "key deve ter"),
        ([_rule(key="a" * 49)], "key deve ter"),
        ([_rule(key="outros")], "reservada"),
        ([_rule(label="")], "label deve ter"),
        ([_rule(label="x" * 81)], "label deve ter"),
        ([_rule(patterns=[])], "patterns deve ter"),
        ([_rule(patterns="abc")], "patterns deve ter"),
        ([_rule(patterns=["x"] * 31)], "patterns deve ter"),
        ([_rule(patterns=["  "])], "cada padrão"),
        ([_rule(patterns=["x" * 201])], "cada padrão"),
        ([_rule(patterns=["(sem fechar"])], "padrão inválido"),
        ([_rule(), _rule()], "Keys repetidas: tema"),
    ],
)
def test_invalid_rules_are_rejected(rules: object, message: str) -> None:
    with pytest.raises(InvalidThemeRulesError, match=message):
        validate_theme_rules(rules)


def test_valid_rules_are_trimmed_and_kept_at_limits() -> None:
    rules = validate_theme_rules(
        [_rule(key="a" * 48, label=" " + "x" * 80 + " ", patterns=[" abc ", "y" * 200])]
    )
    assert rules[0].key == "a" * 48
    assert rules[0].label == "x" * 80
    assert rules[0].patterns == ("abc", "y" * 200)
    assert len(validate_theme_rules([_rule(key=f"t{i}") for i in range(MAX_RULES)])) == 30
