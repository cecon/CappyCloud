# Sandbox — Global Skills Reference

Este arquivo é pensado para ser **injetado em qualquer repositório**.
As referências abaixo apontam apenas para a sandbox compartilhada.

O agente deve trabalhar somente dentro do worktree da conversa ou dos caminhos
absolutos listados no prompt da sessão. Caminhos globais como `/repos/<slug>/`
não fazem parte do escopo da conversa.

## Regras De Evidência

- Responda em português e entregue a conclusão consolidada, não o plano de
  investigação.
- `Grep`, listagem de arquivos e busca textual servem para localizar
  candidatos; não são evidência suficiente para afirmar regra de negócio,
  procedimento, SQL, campo de tabela ou configuração.
- Antes de recomendar procedimento ou citar arquivo como prova, leia o trecho
  exato com `Read`/comando equivalente. Cite somente arquivos/linhas realmente
  abertos na conversa.
- Para SQL, flags, parâmetros e configurações, confirme nomes reais em
  migrations, mappings, XML/Glade, seeds ou consultas existentes. Se o schema
  não estiver comprovado, marque a consulta como template e peça o DDL/log.
- Para suporte operacional, prefira caminho de tela/configuração, sincronização
  oficial, relatório/consulta de validação e coleta de log. Não recomende
  `UPDATE` direto salvo pedido explícito de intervenção técnica de banco.
- Antes de orientar procedimento operacional, identifique a rotina oficial:
  tela/view, endpoint, job configurado ou comando documentado. Se leu apenas
  controller/função interna, continue investigando o chamador.
- Não recomende criar script novo, chamar função interna por shell ou rodar
  código ad hoc como caminho principal, salvo pedido explícito de automação
  técnica.
- Cite caminhos exatamente como vistos no worktree; não adicione prefixos como
  `src/` ou pastas que não apareceram no caminho lido.
- Quando o prompt da sessão listar Confluence para o repo, consulte
  `/confluence/search` antes de responder dúvidas de suporte operacional,
  configuração, cadastro, regra funcional, integração ou procedimento.
- Use `&space=` como filtro primário. `labels` são refinamento opcional; se a
  busca com `labels` retornar zero, erro, timeout ou páginas pouco aderentes,
  repita sem `&labels=`, mantendo `&space=` e termos de busca mais curtos.

## Skills Globais Disponíveis

### Referência Compartilhada

- [global](skills/global/SKILL.md) — Padrões globais de naming, arquitetura hexagonal, tratamento de erros e estrutura de projeto.
- [signoz-observability](skills/signoz-observability/SKILL.md) — Guia de observabilidade com SignOz, incluindo quando não usar (por exemplo, sem `OTEL_SERVICE_NAME`/`service.name`).

## Como Usar no Repo Alvo

### 1) Ler uma skill global

Use caminho da sandbox:

```text
read_file sandbox/skills/global/SKILL.md
read_file sandbox/skills/signoz-observability/SKILL.md
```

### 2) Regra de uso

- Se a skill estiver em `sandbox/skills/<nome>/SKILL.md`, ela é uma skill global.
- O `CLAUDE.md` injetado deve referenciar skills globais usando o prefixo `sandbox/skills/...`.
- Não referenciar paths locais de domínio do projeto (exemplo: `.agents/skills/...`) quando a intenção for skill compartilhada.

### 3) Adicionar nova skill global

```text
sandbox/skills/nova-skill/SKILL.md
```

Frontmatter mínimo:

```yaml
---
name: nova-skill
description: Descrição breve em uma linha
---
```

## Observação Sobre Registro

Cada repositório pode ter seu próprio mecanismo de descoberta/registro.
Quando existir script de registry no repo, execute o script local após criar a skill.

---

Escopo: Global — qualquer repositório com a pasta `sandbox/skills/`
