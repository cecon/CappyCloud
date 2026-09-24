# Skills de desenvolvimento — CappyCloud

Estas são as skills usadas por quem desenvolve o CappyCloud (Claude Code e
Codex). As skills que o **agente do produto** recebe dentro do sandbox são outra
coisa: vêm do banco (Admin → Skills globais e skills de repositório) e estão
descritas no ADR-004.

Cada skill existe em um lugar só. Não há registry: as ferramentas descobrem as
skills pela pasta.

## Onde ficam

| Pasta | Quem carrega sozinho | Conteúdo |
|---|---|---|
| `.agents/skills/` | Codex | Skills de domínio do CappyCloud |
| `.claude/skills/` | Claude Code | Skills de design de terceiros |

No Claude Code, as skills de `.agents/skills/` são lidas sob demanda (o
`CLAUDE.md` pede para ler o `SKILL.md` quando o assunto bater).

### `.agents/skills/`

- `api-ux` — mensagens de erro, SSE e paginação na API FastAPI
- `code-review` — revisão técnica e conformidade com a arquitetura hexagonal
- `create-migration` — migrations Alembic
- `frontend-implementation` — telas React 19
- `service-implementation` — funcionalidades nos serviços backend
- `ux-design` — decisões de UX/UI (dark mode)
- `cappycloud-design-system` — tokens, paletas e padrões de componentes do CappyCloud
- `vulnerability-auditor` — auditoria OWASP
- `prod-container-verify` — conferir o que está rodando em produção
- `speckit-*` — fluxo Spec Kit (specify, clarify, plan, tasks, analyze, implement, …)

### `.claude/skills/`

- `design-system` — arquitetura de tokens, tipografia e espaçamentos
- `ui-styling` — shadcn/ui, Tailwind e componentes acessíveis
- `ui-ux-pro-max` — catálogo de estilos, paletas e guidelines de UI/UX

## Criar uma skill

1. Escolha a pasta pelo público: domínio do CappyCloud em `.agents/skills/`,
   algo que só o Claude Code usa em `.claude/skills/`. Não copie a mesma skill
   para as duas.
2. Crie `<pasta>/<nome>/SKILL.md` com frontmatter:

   ```markdown
   ---
   name: <nome>
   description: Quando usar a skill, em uma linha.
   ---

   # Título

   Instruções, exemplos e limites.
   ```

3. Acrescente a skill na lista acima.

Use nomes em kebab-case e únicos entre as duas pastas.
