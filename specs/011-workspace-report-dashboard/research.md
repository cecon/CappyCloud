# Research: Relatório de uso por workspace

## Amostra real (prod, 2026-10-09, só leitura)

85 conversas com workspace: proteus 29, autosystem 21, seller 15, emsys 10,
smartpos 6, pdvfacil 4 (mais 405 sem workspace, fora do relatório).
`conversations.repos` em workspaces só leitura traz `base_branch` (`main`
no PROTEUS, `master` no EMSYS e no autosystem) e `branch_name` nulo.

Assuntos do proteus (título + primeira mensagem):

- rejeições/falhas de schema da prefeitura de SP (`indDest`, `cLocPrestacao`,
  "1001 - XML não compatível com Schema");
- rejeições por código: E160 (Goiânia, Brasília, Aracaju), E370 (retenções em
  Jundiaí), 651 (IBS);
- emissor nacional (`cod_mun = 9000009`, DPS / Sefin Nacional, Petrópolis);
- motivos de rejeição por prefeitura e versão de layout (Salvador 1.00,
  Mogi das Cruzes 1.01, Aparecida de Goiânia 1.01);
- exploração ("me fale sobre esse projeto") e ruído ("ola").

Nos outros workspaces: configuração/ativação (QRLinx, SAP, menu fiscal),
fiscal (PIS/COFINS, SPED, NF-e, MDF-e, CIAP), banco (tabela, procedure
`sp_*`), integrações (API, Scanntech, Selcon), desempenho (lentidão),
arquitetura e documentação (Lei do Bem, Confluence/Linx Share).

## Revisão — pedido oficial (slide da Diretoria)

O slide do time Protheus define o formato: "Total de consultas" = perguntas,
analistas, custo total e custo médio por consulta em R$, colunas por semana
(blocos de 7 dias desde o início do período) e distribuição por tema em %.

Conferência em prod (só leitura) no mesmo período do slide (01/09 a 08/10/2026):
o proteus tem 36 perguntas de 3 usuários e US$ 18,87 em `messages.cost_usd`; o
slide mostra 428 perguntas, 1 analista e R$ 8,56. Os números do slide não saem
desta base, então a tela da Cappy vai mostrar valores diferentes dos do slide.

**Câmbio**: PTAX venda do Banco Central (API pública Olinda,
`CotacaoDolarPeriodo`), última cotação até o fim do período (janela de 10 dias
para fins de semana e feriados). Cotações passadas ficam em cache no processo.
Falha da fonte → relatório em US$ com aviso. É a única chamada de rede nova da
API.

## Conferência — custo equivale à API da Claude (2026-10-09)

Em prod as conversas rodam no runtime Claude CLI numa assinatura
(`messages.plan_usage` traz os limites de 5 h / 7 dias), que não cobra por
token. O `cost_usd` gravado é o `total_cost_usd` do Claude Code
(`services/sandbox/claude_runtime_mapper.js`), calculado com o catálogo de
preços embutido no CLI, por modelo e tipo de token, incluindo cache.

Catálogo do Claude Code 2.1.281 (sandbox de prod) comparado à página oficial
https://platform.claude.com/docs/en/about-claude/pricing (US$/MTok):

| Modelo | Entrada | Cache 5 min | Cache 1 h | Leitura de cache | Saída | Confere |
|---|---|---|---|---|---|---|
| Claude Opus 5.5 | 4 | 5 | 8 | 0,20 | 20 | sim |
| Claude Sonnet 5 | 2 | 2,50 | 4 | 0,20 | 10 | sim |

Modelos usados nas conversas com workspace em prod: `claude-sonnet-5` (127
respostas), `claude-opus-5-5` (15) e um `gpt-5.4` (1, via OpenRouter, preço do
OpenRouter). Por isso o relatório usa `cost_usd` sem recálculo e diz que é o
custo pela tabela da API da Claude. A base não guarda a quebra entre entrada,
leitura e gravação de cache (`prompt_tokens` soma as três), então não dá para
recalcular por fora; se um dia for preciso, o runtime teria de gravar essa quebra.

## Decisão 1 — Classificação por regras, não por LLM

- **Escolha**: lista ordenada de temas, cada um com expressões regulares,
  aplicadas ao título + primeira mensagem do usuário, sem diferença de
  maiúsculas e acentos. Primeiro tema que casar vence; sem casamento, "Outros".
- **Por quê**: custo zero, determinístico (o mesmo filtro dá o mesmo número na
  tela, na planilha e no PDF), auditável (a regra explica o tema) e editável.
- **Alternativa — LLM**: um classificador barato (ex.: um modelo pequeno no
  OpenRouter) por conversa custaria algo como 1–2 mil tokens de entrada por
  consulta; o custo real dependeria do preço do catálogo OpenRouter no dia e
  teria de ser gravado como custo do relatório. Fica como evolução opcional,
  gravando o tema na conversa para não reclassificar a cada relatório. Não
  implementado.

## Decisão 2 — Modelos prontos + regras próprias por workspace

- Duas colunas em `workspaces`: `report_theme_preset` (nome de um modelo pronto
  no código) e `report_themes` (regras próprias em JSON).
- Resolução: regras próprias → modelo do workspace → modelo `generico`.
- A migration aponta o proteus para o modelo `protheus-tss` (formato da Diretoria); nada mais é
  específico de workspace no código.
- Só o super admin edita (JSON validado: chave em slug, regex que compila,
  até 30 temas, até 30 padrões de até 200 caracteres).

### Modelo `por-assunto` (opcional; era o `generico` inicial)

| Ordem | Chave | Rótulo | Exemplos de padrão |
|------|-------|--------|---------------------|
| 1 | desempenho | Desempenho / lentidão | `lent(o|a|idao)`, `demor`, `performance`, `timeout` |
| 2 | erro-rejeicao | Erro / rejeição | `rejei`, `\berros?\b`, `falha`, `exception`, `\be\d{3}\b` |
| 3 | fiscal | Fiscal / tributário | `\bnf[cs]?-?e\b`, `sped`, `icms`, `pis`, `cofins`, `ibs`, `cbs`, `tribut`, `ciap`, `mdf-?e`, `fiscal` |
| 4 | integracao | Integração / API | `\bapi\b`, `integra`, `webhook`, `sincron` |
| 5 | dados | Banco de dados / consultas | `tabela`, `procedure`, `\bsp_`, `\bsql\b`, `consulta` |
| 6 | configuracao | Configuração / parâmetros | `configura`, `parametr`, `\bativ(ar|amos|o)\b`, `habilit`, `\bmenu\b`, `atalho` |
| 7 | arquitetura | Arquitetura / visão do projeto | `arquitetura`, `\bstacks?\b`, `projeto`, `fluxo`, `rotina` |
| 8 | documentacao | Documentação / relatório técnico | `documenta`, `confluence`, `linx ?share`, `artigo`, `lei do bem` |

### Modelo `nfse-detalhado` (opcional; era `nfse-protheus`)

| Ordem | Chave | Rótulo | Exemplos de padrão |
|------|-------|--------|---------------------|
| 1 | nfse-emissor-nacional | NFS-e: Emissor / padrão nacional | `emissor nacional`, `padrao nacional`, `sefin`, `\bdps\b`, `9000009` |
| 2 | nfse-reforma-tributaria | NFS-e: Reforma tributária (IBS/CBS) | `\bibs\b`, `\bcbs\b`, `ibscbs`, `classificacao tributaria`, `_rt\b` |
| 3 | nfse-retencoes | NFS-e: Retenções e ISS | `retenc`, `retid[oa]`, `\biss\b`, `deduc`, `vdedred` |
| 4 | nfse-schema-xml | NFS-e: Schema / layout XML | `schema`, `layout`, `\bxml\b`, `\btag\b`, `element`, `inddest`, `clocprestacao` |
| 5 | nfse-rejeicao-codigo | NFS-e: Rejeição por código | `rejei`, `\be\d{3}\b`, `\b\d{3,4} ?- `, `falha`, `\berros?\b` |
| 6 | visao-projeto | Visão geral / exploração | `(sobre|explique?) (esse|este|o) projeto`, `arquitetura`, `\bstacks?\b` |

A ordem põe o assunto mais específico antes: a E370 é rejeição, mas o assunto
é retenção; a E160 é rejeição, mas o assunto é schema. Na amostra do proteus,
todas as consultas técnicas caem num tema; só "ola" e "Analise sem o PDF
mesmo" vão para "Outros".

"Por prefeitura" é outra dimensão (cruza com qualquer tema) e fica como
evolução: extrair o município do texto exige lista de municípios.

### Modelos no formato da Diretoria (atuais)

`generico` (todos os workspaces) e `protheus-tss` (proteus, via migration) usam
as chaves do slide, nesta ordem: `erros-rejeicoes`, `analise-codigo`,
`configuracoes`, `validacoes-regras`, `duvidas-gerais` e, sem casamento,
`outros`. O `protheus-tss` usa rótulos e padrões do Protheus/TSS (`.prw`,
`advpl`, `MV_`, `tssnewnfse`, `cod_mun`, ISS, IBS/CBS, retenções). Os padrões
estão em `services/api/app/domain/report_theme_presets.py`.

## Decisão 3 — Agregação em Python sobre mensagens do período

- A port devolve as mensagens do período (conversa, data, custo) e os dados das
  conversas; semanas ISO, fuso e médias são calculados no use case.
- **Por quê**: o fuso America/Sao_Paulo e a semana ISO não têm SQL portável
  entre Postgres e o SQLite dos testes; o volume atual é pequeno.
- **Alternativa**: `date_trunc('week', created_at AT TIME ZONE …)` no Postgres;
  fica para quando o volume pedir.

## Decisão 4 — Exportação

- XLSX (openpyxl, já instalado) com abas Resumo, Analistas, Semanas, Temas,
  Consultas; CSV `;` com BOM (mesmo padrão do `tickets.csv`) só das consultas.
- PDF pela página imprimível (`/admin/reports/print?…`) e o "Salvar como PDF"
  do navegador; sem dependência nova de PDF no servidor.
- Só US$. Sem fonte de câmbio configurada, R$ fica fora.
