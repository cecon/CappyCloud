# Decisões Arquiteturais

Este diretório registra decisões que devem guiar mudanças futuras no
CappyCloud. Antes de alterar runtime, isolamento, integração com agente,
contratos de API ou ferramentas do sandbox, consulte as ADRs relacionadas.

| ADR | Status | Tema |
|-----|--------|------|
| [ADR-001](adr-001-hexagonal-architecture.md) | Aceite | Arquitetura Hexagonal da API |
| [ADR-002](adr-002-sandbox-runtime-and-worktree-sessions.md) | Aceite | Runtime sandbox e sessões por worktree |
| [ADR-003](adr-003-on-demand-semantic-code-tooling.md) | Aceite | Ferramentas semânticas LSP/AST sob demanda |

## Como usar

- Crie uma nova ADR quando a decisão tiver trade-off real e afetar atividades
  futuras.
- Prefira registrar decisão, contexto, alternativas e consequências.
- Atualize `docs/ARCHITECTURE.md` quando a ADR mudar o mapa operacional do
  sistema.
