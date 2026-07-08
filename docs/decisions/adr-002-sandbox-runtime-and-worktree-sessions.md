# ADR-002 — Runtime Sandbox e Sessões por Worktree

**Status:** Aceite
**Data:** 2026-05-16
**Contexto:** CappyCloud — execução de agentes em repositórios dinâmicos

---

## Contexto

O CappyCloud precisa executar agentes contra repositórios que mudam por
ambiente, cliente, squad ou demonstração. Esses repositórios não devem ser
tratados como infraestrutura fixa do deploy.

Também precisamos manter isolamento operacional entre conversas, preservar
histórico, permitir múltiplos repositórios em uma mesma sessão e evitar que a API
precise montar worktrees diretamente no host.

---

## Decisão

Usar um ou mais containers sandbox registrados, cada um rodando:

- `openclaude` em modo gRPC headless;
- `session_server.js` como sidecar HTTP para preparar repositórios, worktrees e
  operações Git;
- volume persistente em `/repos`.

Cada conversa recebe um `session_root` transitório em:

```text
/repos/sessions/<session_id>/
```

Dentro dele, cada repositório selecionado pela conversa ganha um worktree
próprio:

```text
/repos/sessions/<session_id>/<repo-alias>/
```

A partir da spec `006-persistent-user-workspaces`, o sandbox tambem pode manter
um baseline persistente por usuario, repositorio, sandbox e branch base em:

```text
/repos/users/<user>/<sandbox>/<repo>/<branch>/
```

Esse baseline e preparado pelo endpoint interno `/user-workspaces/ensure`. Ele
serve como fonte limpa para novas sessoes, mas nao substitui o worktree de
conversa. Quando `source_workspace_path` e enviado no payload de `/sessions`, o
`session_server` valida que o baseline esta dentro de `/repos/users/`, existe e
esta limpo; em seguida cria o worktree da conversa dentro de `/repos/sessions/`
a partir do commit desse baseline.

A API não usa Docker socket para manipular worktrees. Ela conversa com o
`session_server` do sandbox por HTTP interno e com o agente por gRPC.

---

## Regras derivadas

1. Repositórios cadastrados são catálogo do ambiente, não parte fixa do código.
2. A conversa seleciona quais repositórios entram no contexto.
3. O sandbox materializa worktrees por conversa e por repositório.
4. Operações Git/worktree passam pelo `session_server`, não pela API.
5. O agente deve operar no worktree da sessão, não no clone principal.
6. O baseline persistente por usuario nao deve receber edicoes de conversas.
7. Sessões podem ser descartadas por TTL sem apagar histórico da conversa.
8. MCPs, skills e modelo são contexto de execução e podem variar por usuário ou
   conversa.
9. Regras específicas de produto, cliente ou repositório devem viver em skills,
   documentação externa configurada ou dados do banco. Não devem entrar no
   prompt global, no prefetch ou no sandbox como conhecimento rígido.
10. Fontes documentais externas devem ser configuráveis por ambiente; defaults
   de compatibilidade não podem ser tratados como regra de produto.

---

## Consequências

### Positivas

- Conversas ficam isoladas sem clonar o repositório inteiro a cada mensagem.
- Conversas repetidas do mesmo usuario podem reaproveitar baseline preparado sem
  compartilhar arquivos nao commitados com outros usuarios.
- O runtime suporta múltiplos repositórios por conversa.
- A API fica desacoplada do filesystem interno do sandbox.
- É possível reconstruir sessão de forma idempotente quando o volume ou worktree
  foi limpo.

### Negativas / Trade-offs

- O `session_server` vira componente crítico do runtime.
- Bugs de path/worktree podem produzir falsos negativos do agente se a sessão
  não for validada antes da chamada gRPC.
- O volume `/repos` precisa ser gerido com cuidado para evitar acúmulo de
  worktrees antigos.

---

## Alternativas consideradas

### Um container por repositório

Rejeitado para o desenho atual. Facilita isolamento conceitual, mas encarece
memória/CPU, dificulta conversas multi-repo e acopla cadastro de repositório ao
ciclo de vida de container.

### Clonar repositório por conversa

Rejeitado como padrão. É simples, mas lento e caro em disco para repositórios
grandes. Worktrees aproveitam o clone persistente e mantêm isolamento de branch.

### Executar worktrees diretamente no host da API

Rejeitado por isolamento. O agente e ferramentas devem rodar no sandbox; a API
orquestra, mas não deve virar ambiente de execução do código do usuário.

---

## Referências

- `services/cappycloud_agent/_environment_manager.py`
- `services/cappycloud_agent/_session_store.py`
- `services/sandbox/session_server.js`
- `services/sandbox/session_start.sh`
- `docs/how-to/agent-runtime-context.md`
- `docs/how-to/debug-agent.md`
