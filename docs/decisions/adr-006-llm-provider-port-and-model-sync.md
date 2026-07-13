# ADR-006 — LLM Provider como Porta e Sincronização de Modelos

**Status:** Proposta
**Data:** 2026-05-16
**Contexto:** CappyCloud — suporte a múltiplos provedores LLM (OpenRouter, Azure AI Foundry, e futuros) com modelos dinâmicos liberados por usuário

---

## Contexto

Hoje a integração com LLM passa por openclaude rodando dentro da sandbox
([ADR-002](adr-002-sandbox-runtime-and-worktree-sessions.md)). O provedor
upstream é fixo (OpenRouter via configuração estática). Não há:

- Cadastro de modelos em banco — a lista é o que o provider expõe na hora.
- Controle de quais modelos um usuário pode escolher (livre vs. restrito a
  modelos gratuitos, por exemplo).
- Abstração sobre o provedor — trocar OpenRouter por Azure AI Foundry hoje
  exige editar código em vários pontos.

Os requisitos novos são:

1. Usuário escolhe modelo antes de iniciar conversa, com lista filtrada por
   permissão (ver [ADR-005](adr-005-roles-and-binary-permissions.md)).
2. Modelos podem ser sincronizados a partir da API do provider (OpenRouter
   expõe `/models`, Azure AI Foundry expõe deployments por assinatura).
3. A camada de aplicação não pode acoplar a um provider específico —
   adicionar Azure AI Foundry no futuro não deve exigir refator profundo.

---

## Decisão

### 1. Provider como entidade cadastrável

Tabela `LlmProvider` representa cada conexão a um provedor:

```text
LlmProvider:
  + id
  + kind (openrouter | azure_ai_foundry | ...)
  + name (livre, ex: "OpenRouter prod", "Azure tenant XYZ")
  + base_url
  + api_key_secret_ref (referência a segredo; não armazenamos a chave em texto)
  + enabled
  + last_synced_at
```

Vários providers podem coexistir. Sandbox referencia 1 provider via
`Sandbox.llm_provider_id` (ou seleção por conversa — definido na
implementação).

### 2. Modelos catalogados em banco

Tabela `Model`:

```text
Model:
  + id
  + provider_id (FK LlmProvider)
  + slug (identificador no provider, ex: "anthropic/claude-3.5-sonnet")
  + display_name
  + tier (free | paid | unknown)
  + context_window (int, nullable)
  + capabilities (JSON: tools, vision, etc.)
  + last_seen_at (preenchido no sync)
  + enabled (admin pode esconder modelos sem revogar acesso)
```

A combinação `(provider_id, slug)` é única. Modelos não vistos no último
sync ficam com `last_seen_at` antigo e podem ser sinalizados na UI como
deprecados.

### 3. Permissão de modelo por usuário

`UserModelAccess(user_id, model_id)` — tabela binária, igual ao padrão de
[ADR-005](adr-005-roles-and-binary-permissions.md). Sem níveis. ADMIN
ignora a tabela e vê todos.

Bulk-assign por tier é prática esperada: "atribuir todos os modelos `free`
para o usuário X" deve ser ação de um clique na UI admin.

### 4. Port `LlmProviderGateway`

Abstração que define o contrato que cada adapter implementa:

```python
class LlmProviderGateway(Protocol):
    def list_models(self) -> list[ModelMetadata]: ...
    def health_check(self) -> ProviderHealth: ...
    # chat completions ficam fora do escopo desta ADR — openclaude
    # continua sendo o caminho de inferência. Esta porta cobre apenas
    # catálogo e configuração.
```

Adapters iniciais:

- `OpenRouterAdapter`: chama `GET https://openrouter.ai/api/v1/models`.
- `AzureAiFoundryAdapter`: stub nesta ADR; implementado quando demandado.

A inferência continua via openclaude dentro do sandbox. O que muda é como o
openclaude é configurado: o bootstrap (ADR-004) recebe `provider.base_url` e
`provider.api_key` e escreve no `settings.json`/env do openclaude.

### 5. Sincronização de modelos

Ação `sync_models(provider_id)`:

1. Adapter chama API do provider e retorna lista de modelos.
2. Use case faz upsert em `Model`: novos → insert; existentes → update
   `display_name`, `tier`, `capabilities`, `last_seen_at`.
3. Modelos não presentes na resposta não são deletados — só envelhecem
   `last_seen_at` (preserva permissões existentes mesmo se o provider
   esconder temporariamente).
4. `LlmProvider.last_synced_at` é atualizado ao final.

Disparo:

- Manual: botão "Sincronizar agora" na UI admin do provider.
- Agendado: tarefa periódica (intervalo configurável; default 6h).
- Defensivo: se admin abre a UI e `last_synced_at` está velho (> 24h),
  sugere sync.

### 6. Tier `free` derivado do provider

OpenRouter expõe campo de preço por modelo. `tier = free` quando preço de
input + output for zero. Para Azure AI Foundry, tier vem do plano da
assinatura. Cada adapter é responsável por mapear seus campos para o tier
canônico do CappyCloud.

### 7. Fluxo no start de conversa

Reforço do que ficou em [ADR-004](adr-004-sandbox-lifecycle-and-registry.md):

1. UI mostra dropdown de modelos filtrados por `UserModelAccess` e pela
   sandbox selecionada (modelos do provider configurado na sandbox).
2. API valida no guard: `user` tem acesso a `model_id`?`model` pertence ao
   provider configurado na `sandbox`?
3. Bootstrap injeta `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL` e modelo
   default no openclaude da sandbox.

---

## Regras derivadas

1. Nenhum componente da aplicação consome SDK do OpenRouter (ou de outro
   provider) diretamente — sempre via `LlmProviderGateway`.
2. Chaves de API ficam em armazenamento de segredo (Vault, env, secret
   manager do orquestrador). O DB guarda referência, não a chave em si.
3. Modelos são case-sensitive pelo `slug` do provider. Não há normalização
   além de trim.
4. Sync não bloqueia. Falha de sync registra erro mas não falha o boot da
   sandbox — usa-se o catálogo cacheado.
5. Adicionar provider novo = novo adapter implementando `LlmProviderGateway`
   + entrada no enum `kind`. Não exige mudança em UI/use cases.
6. UI admin lista providers, mostra `last_synced_at`, status de health,
   contagem de modelos catalogados.
7. Quando um modelo é desabilitado (`enabled=false`), ele some dos dropdowns
   mas as permissões `UserModelAccess` ficam (reativar restaura
   automaticamente).

---

## Consequências

### Positivas

- Trocar/agregar provider vira tarefa isolada: 1 adapter + 1 entrada no
  enum.
- Catálogo de modelos fica auditável e versionado (admin sabe o que existe).
- Permissão por modelo dá granularidade sem complicar o modelo geral.
- Suporte a múltiplas assinaturas/contas no mesmo CappyCloud (1 provider
  por sandbox ou por tenant).

### Negativas / Trade-offs

- Catálogo em DB pode ficar fora de sincronia com o provider entre syncs.
  Mitigação: indicador visual de "última sync" e botão de sync manual.
- Tier derivado é heurística — providers podem ter modelos pagos com preço
  promocional zero, ou modelos free com cota. UI deve deixar claro que
  `tier` é referência, não garantia.
- Inferência ainda passa por openclaude. Esta ADR não cobre o caminho de
  trocar o engine de inferência (openclaude → SDK direto). Quando for o
  caso, será nova ADR.

---

## Alternativas consideradas

### Hardcodar OpenRouter

Status atual. Rejeitado porque já temos pedido explícito de suporte a
Azure AI Foundry, e código acoplado a um provider é caro de remover.

### Lista de modelos vinda só da API, sem cache em DB

Rejeitado. Quebra se o provider estiver fora do ar; impede permissão por
modelo (sem ID estável em DB para usar como FK); impede filtros e busca
eficientes na UI.

### Permissão por tier em vez de por modelo

Considerado. Funcionaria para "USER só pode usar free". Rejeitado como
modelo único porque tira flexibilidade (não conseguiria liberar 1 modelo
pago específico para 1 usuário). A solução adotada permite atribuição por
tier via bulk-action, mantendo granularidade quando necessária.

### Adapter genérico OpenAI-compatible

Tentador (OpenRouter e várias outras APIs falam OpenAI-compat). Rejeitado
como primeiro passo porque cada provider tem extensões e quirks
(pricing, deployments do Azure, headers de fallback do OpenRouter) que
um adapter genérico esconderia. Adapters por provider são mais simples
e explícitos.

---

## Referências

- [ADR-002](adr-002-sandbox-runtime-and-worktree-sessions.md) — runtime do agente
- [ADR-004](adr-004-sandbox-lifecycle-and-registry.md) — bootstrap da sandbox
- [ADR-005](adr-005-roles-and-binary-permissions.md) — permissões binárias
- OpenRouter Models API — https://openrouter.ai/docs/api-reference/list-available-models
