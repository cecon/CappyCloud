# Skills System — CappyCloud

## Overview

O CappyCloud usa um sistema modular de **skills** que são capacidades especializadas para diferentes tipos de trabalho. As skills são autodescobiertas e catalogadas em um registry centralizado.

## Estrutura

```
.agents/skills/           # Skills para agentes (automação e tarefas complexas)
  ├── api-ux/            # Melhorias UX em FastAPI
  ├── code-review/       # Revisão de código técnica
  ├── create-migration/  # Criação de migrations
  ├── frontend-implementation/  # Componentes React
  ├── service-implementation/   # Backend services
  ├── ux-design/         # Decisões UX/UI
  └── vulnerability-auditor/   # Auditoria de segurança

.claude/skills/           # Skills para Claude (design e interface)
  ├── design-system/     # Design tokens e arquitetura visual
  ├── ui-styling/        # Componentes e estilos
  └── ui-ux-pro-max/     # Design intelligence avançado
```

## Registry Central

Todas as skills são registradas em [skills-registry.json](../skills-registry.json):

```json
{
  "version": "1.0",
  "lastUpdated": "2026-05-13T...",
  "totalSkills": 10,
  "skills": {
    "api-ux": {
      "name": "api-ux",
      "path": ".agents/skills/api-ux",
      "file": ".agents/skills/api-ux/SKILL.md",
      "category": "agents",
      "description": "Use esta habilidade para melhorar a experiência..."
    },
    ...
  }
}
```

## Criar uma Nova Skill

1. **Criar diretório:**
   ```bash
   mkdir -p .agents/skills/my-skill
   # ou para Claude
   mkdir -p .claude/skills/my-skill
   ```

2. **Criar SKILL.md com frontmatter:**
   ```markdown
   ---
   name: my-skill
   description: Descrição clara da skill em uma linha
   ---

   # Descrição detalhada da skill

   Explicar quando usar, exemplos de uso, etc.
   ```

3. **Atualizar registry:**
   ```bash
   python3 scripts/update-skills-registry.py
   ```

4. **Verificar CLAUDE.md:** Adicionar a skill na seção apropriada do [CLAUDE.md](../CLAUDE.md)

## Manter Registry Atualizado

**Manualmente:**
```bash
python3 scripts/update-skills-registry.py
```

**Automaticamente (via git hook):**
O arquivo `.git/hooks/pre-commit` pode ser configurado para atualizar o registry antes de cada commit.

## Referenciar Skills no Código

No `CLAUDE.md` ou em prompts:

```markdown
**Skills Disponíveis:**
- [api-ux](.agents/skills/api-ux/SKILL.md)
- [code-review](.agents/skills/code-review/SKILL.md)
```

Ou via registry JSON:
```json
{
  "skillName": "api-ux",
  "skillFile": ".agents/skills/api-ux/SKILL.md"
}
```

## Boas Práticas

✅ **Faça:**
- Usar nomes descritivos e em lowercase com hífens (kebab-case)
- Adicionar frontmatter YAML com `name` e `description`
- Manter descrição concisa (máx 150 caracteres)
- Organizar skills por categoria (agents vs claude)
- Atualizar registry após adicionar/remover skills

❌ **Não Faça:**
- Criar skills sem frontmatter
- Usar espaços ou caracteres especiais em nomes
- Deixar registry desatualizado
- Duplicar skills entre categorias

## Status Atual

📊 **10 Skills Registradas:**

**Agents (7):**
- api-ux
- code-review
- create-migration
- frontend-implementation
- service-implementation
- ux-design
- vulnerability-auditor

**Claude (3):**
- design-system
- ui-styling
- ui-ux-pro-max

Último update: 2026-05-13
