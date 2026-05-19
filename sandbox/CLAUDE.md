# Sandbox — Global Skills Reference

Este arquivo é pensado para ser **injetado em qualquer repositório**.
As referências abaixo apontam apenas para a sandbox compartilhada.

O agente deve trabalhar somente dentro do worktree da conversa ou dos caminhos
absolutos listados no prompt da sessão. Caminhos globais como `/repos/<slug>/`
não fazem parte do escopo da conversa.

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
