# Spec Kit no CappyCloud

O CappyCloud usa Spec Kit para conduzir mudancas nao triviais por
especificacao antes da implementacao. A instalacao local usa a integracao Codex
em modo skills.

## Onde fica

- `.specify/memory/constitution.md`: principios obrigatorios do projeto.
- `.specify/templates/`: templates oficiais de spec, plano, tarefas e
  checklists.
- `.specify/scripts/powershell/`: scripts usados pelos comandos no Windows.
- `.agents/skills/speckit-*/SKILL.md`: skills Codex geradas a partir dos
  comandos oficiais do Spec Kit.
- `specs/`: diretorio esperado para specs de features.

## Fluxo padrao

1. `$speckit-specify`: cria ou atualiza a especificacao a partir da necessidade.
2. `$speckit-clarify`: resolve lacunas relevantes antes do plano.
3. `$speckit-plan`: gera o plano tecnico e checa a constituicao.
4. `$speckit-tasks`: quebra o plano em tarefas executaveis.
5. `$speckit-analyze`: procura inconsistencias entre spec, plano e tarefas.
6. `$speckit-implement`: executa as tarefas.

Use esse fluxo para features, mudancas de arquitetura, alteracoes de contrato
de API, alteracoes em permissao/autorizacao, UX relevante, agente, sandbox,
banco ou custo/modelos.

Para bug pequeno ou ajuste operacional claro, o fluxo direto ainda e aceitavel,
desde que a resposta cite a evidencia tecnica e preserve os gates do repo.

## Gates obrigatorios

Siga `docs/AGENT_RULES.md`. Em resumo:

- backend: `ruff check`, `ruff format --check`, `mypy app/`, `pytest`;
- frontend: lint/build do `web/` quando houver alteracao em UI;
- cobertura minima: 80%;
- regra de negocio em `services/api/app/application/use_cases/`;
- routers HTTP sem SQL ou regra de dominio;
- novas ports com adapter real, fake e testes de contrato quando aplicavel.

## Atualizacao do Spec Kit

A versao instalada foi baseada no Spec Kit `0.10.1` com integracao `codex`,
script `ps` e skills habilitadas. Para atualizar no futuro, rode o upgrade do
Spec Kit em uma branch separada e revise principalmente:

- `.specify/templates/`;
- `.specify/scripts/powershell/`;
- `.agents/skills/speckit-*/SKILL.md`;
- `.specify/memory/constitution.md`, que deve preservar as regras do
  CappyCloud.
