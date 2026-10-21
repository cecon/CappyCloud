"""Modelos prontos de temas do relatório (dados puros, validados em ``report_themes``).

``generico`` e ``protheus-tss`` seguem a taxonomia do relatório que o time
Protheus leva à Diretoria (Erros/Rejeições, Análise de código, Configurações,
Validações e regras de negócio, Dúvidas gerais, Outros). ``nfse-detalhado`` e
``por-assunto`` quebram em assuntos mais finos. Ordem importa: o primeiro tema
que casar vence; "Dúvidas gerais" fica por último porque casa quase tudo.
"""

from __future__ import annotations

from typing import Any

Rule = dict[str, Any]

_QUESTION = [r"\?", r"\b(como|qual|quais|existe|onde|o que|por que|pergunta)\b", r"duvida"]

GENERICO: list[Rule] = [
    {
        "key": "erros-rejeicoes",
        "label": "Erros / Rejeições",
        "patterns": [
            r"rejei",
            r"\berros?\b",
            r"falha",
            r"exception",
            r"\be\d{3}\b",
            r"\bbug\b",
            r"nao funciona",
            r"\blent(o|a|idao)\b",
            r"travad",
        ],
    },
    {
        "key": "analise-codigo",
        "label": "Análise de código",
        "patterns": [
            r"codigo",
            r"\bfontes?\b",
            r"\bfuncao\b",
            r"\bmetodo\b",
            r"\bclasse\b",
            r"procedure",
            r"\bsp_",
            r"rotina",
            r"fluxo",
            r"arquitetura",
            r"\bstacks?\b",
            r"tabela",
        ],
    },
    {
        "key": "configuracoes",
        "label": "Configurações / Parâmetros",
        "patterns": [
            r"configura",
            r"parametr",
            r"\bativ(ar|amos|o)\b",
            r"habilit",
            r"\bmenu\b",
            r"cadastr",
            r"atalho",
        ],
    },
    {
        "key": "validacoes-regras",
        "label": "Validações e regras de negócio",
        "patterns": [
            r"valida",
            r"\bregras?\b",
            r"calculo",
            r"tribut",
            r"\bicms\b",
            r"\bpis\b",
            r"\bcofins\b",
            r"\bibs\b",
            r"\bcbs\b",
            r"reten",
            r"aliquota",
            r"fiscal",
            r"\bnf[cs]?-?e\b",
            r"\bsped\b",
        ],
    },
    {"key": "duvidas-gerais", "label": "Dúvidas gerais", "patterns": [*_QUESTION, r"documenta"]},
]

PROTHEUS_TSS: list[Rule] = [
    {
        "key": "erros-rejeicoes",
        "label": "Erros de emissão / Rejeições",
        "patterns": [
            r"rejei",
            r"\berros?\b",
            r"falha",
            r"\be\d{3}\b",
            r"\b\d{3,4} ?- ",
            r"schema",
            r"exception",
            r"nao (transmit|autoriz)",
        ],
    },
    {
        "key": "analise-codigo",
        "label": "Análise de código (Protheus/TSS)",
        "patterns": [
            r"codigo",
            r"\bfontes?\b",
            r"\.prw\b",
            r"\.tlpp\b",
            r"advpl",
            r"\bfuncao\b",
            r"\bmetodo\b",
            r"\bclasse\b",
            r"ponto de entrada",
            r"rotina",
            r"fluxo",
            r"arquitetura",
        ],
    },
    {
        "key": "configuracoes",
        "label": "Configurações / Parâmetros",
        "patterns": [
            r"configura",
            r"parametr",
            r"\bmv_",
            r"tssnewnfse",
            r"cod_mun",
            r"\bativ(ar|o)\b",
            r"habilit",
            r"cadastr",
        ],
    },
    {
        "key": "validacoes-regras",
        "label": "Validações e regras de negócio",
        "patterns": [
            r"valida",
            r"\bregras?\b",
            r"reten",
            r"\biss\b",
            r"\bibs\b",
            r"\bcbs\b",
            r"tribut",
            r"deduc",
            r"aliquota",
            r"base de calculo",
            r"inddest",
            r"tomador",
        ],
    },
    {
        "key": "duvidas-gerais",
        "label": "Dúvidas gerais",
        "patterns": [*_QUESTION, r"me (fale|explique)", r"projeto"],
    },
]

NFSE_DETALHADO: list[Rule] = [
    {
        "key": "nfse-emissor-nacional",
        "label": "NFS-e: Emissor / padrão nacional",
        "patterns": [r"emissor nacional", r"padrao nacional", r"sefin", r"\bdps\b", r"9000009"],
    },
    {
        "key": "nfse-reforma-tributaria",
        "label": "NFS-e: Reforma tributária (IBS/CBS)",
        "patterns": [
            r"\bibs\b",
            r"\bcbs\b",
            r"ibscbs",
            r"classificacao tributaria",
            r"reforma tributaria",
            r"_rt\b",
        ],
    },
    {
        "key": "nfse-retencoes",
        "label": "NFS-e: Retenções e ISS",
        "patterns": [r"retenc", r"retid[oa]", r"\biss\b", r"deduc", r"vdedred"],
    },
    {
        "key": "nfse-schema-xml",
        "label": "NFS-e: Schema / layout XML",
        "patterns": [
            r"schema",
            r"layout",
            r"\bxml\b",
            r"\btag\b",
            r"element",
            r"inddest",
            r"clocprestacao",
        ],
    },
    {
        "key": "nfse-rejeicao-codigo",
        "label": "NFS-e: Rejeição por código",
        "patterns": [r"rejei", r"\be\d{3}\b", r"\b\d{3,4} ?- ", r"falha", r"\berros?\b"],
    },
    {
        "key": "visao-projeto",
        "label": "Visão geral / exploração",
        "patterns": [r"(sobre|explique?) (esse|este|o) projeto", r"arquitetura", r"\bstacks?\b"],
    },
]

POR_ASSUNTO: list[Rule] = [
    {
        "key": "desempenho",
        "label": "Desempenho / lentidão",
        "patterns": [r"\blent(o|a|idao)\b", r"demor", r"performance", r"timeout"],
    },
    {
        "key": "erro-rejeicao",
        "label": "Erro / rejeição",
        "patterns": [r"rejei", r"\berros?\b", r"falha", r"exception", r"\be\d{3}\b"],
    },
    {
        "key": "fiscal",
        "label": "Fiscal / tributário",
        "patterns": [
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
        ],
    },
    {
        "key": "integracao",
        "label": "Integração / API",
        "patterns": [r"\bapis?\b", r"integra", r"webhook", r"sincron"],
    },
    {
        "key": "dados",
        "label": "Banco de dados / consultas",
        "patterns": [r"tabela", r"procedure", r"\bsp_", r"\bsql\b", r"consulta"],
    },
    {
        "key": "configuracao",
        "label": "Configuração / parâmetros",
        "patterns": [
            r"configura",
            r"parametr",
            r"\bativ(ar|amos|o)\b",
            r"habilit",
            r"\bmenu\b",
            r"atalho",
        ],
    },
    {
        "key": "arquitetura",
        "label": "Arquitetura / visão do projeto",
        "patterns": [r"arquitetura", r"\bstacks?\b", r"projeto", r"fluxo", r"rotina"],
    },
    {
        "key": "documentacao",
        "label": "Documentação / relatório técnico",
        "patterns": [r"documenta", r"confluence", r"linx ?share", r"artigo", r"lei do bem"],
    },
]

# chave → (rótulo do modelo, regras)
PRESET_DATA: dict[str, tuple[str, list[Rule]]] = {
    "generico": ("Genérico (formato Diretoria)", GENERICO),
    "protheus-tss": ("Protheus / TSS (formato Diretoria)", PROTHEUS_TSS),
    "nfse-detalhado": ("NFS-e detalhado", NFSE_DETALHADO),
    "por-assunto": ("Por assunto técnico", POR_ASSUNTO),
}
