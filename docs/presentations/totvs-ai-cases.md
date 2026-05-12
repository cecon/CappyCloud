# Cappy — Plataforma de Agentes IA

> Fórum TOTVS · Cases de IA · 15 minutos · Arquitetos + Executivos

Foco: **capacidades técnicas** da plataforma e como ela sustenta os mesmos
casos de uso que a TOTVS está construindo internamente — só que de forma
multi-agente, multi-tenant e desacoplada de modelo.

---

## Slide 1 — Capa (30s)

# Cappy
### Plataforma de Agentes IA com Sandbox Isolado

> Apresentado por: \<seu nome>
> Fórum de Cases de IA · TOTVS · 2026

<!--
Nota de palco:
"Boa tarde. Nos próximos 15 minutos vou mostrar a Cappy: a plataforma que
construímos pra rodar agentes de IA dentro de containers isolados, e como
ela se encaixa nos casos de uso que vocês já estão explorando aqui."
-->

---

## Slide 2 — O problema (90s)

### Cada novo agente está reinventando a mesma infra

- Isolamento entre clientes/franquias → Docker, rede, limites
- Sessão que sobrevive a refresh → estado em Redis/PG, retomada
- Streaming de resposta → gRPC bidirecional, backpressure
- Troca de modelo (Claude, GPT, Llama) → gateway, fallback
- Human-in-the-loop → pausar agente, esperar input, retomar

> **Resultado:** cada iniciativa começa do zero. Um chatbot pra MIT, outro pra
> release notes, outro pra suporte — cada um com sua stack.

<!--
Nota de palco:
"Olhei o slide das iniciativas que foi apresentado: Produtividade Implantação,
Chatbot Protheus, Assistente Release. Todos resolvem problemas diferentes,
mas todos esbarram no mesmo problema de infra. É aqui que a Cappy entra."
-->

---

## Slide 3 — Cappy em uma frase (60s)

### Cappy é a infraestrutura que sustenta agentes — não é mais um chatbot.

```
Browser → API (FastAPI) → Container Docker isolado (1 por usuário+conversa)
                            └─ Agente openclaude (gRPC)
                                  └─ Modelo via OpenRouter (Claude/GPT/...)
```

- 1 container por par `(user_id, chat_id)`
- Git worktree por conversa — agente tem workspace real, não só prompt
- Sessão persistida em Redis (TTL) + PostgreSQL (histórico)
- Streaming gRPC bidirecional com retomada por `ActionRequired`

<!--
Nota de palco:
"Cappy não compete com o Chatbot Protheus — Cappy é o que estaria ABAIXO
de um Chatbot Protheus se ele rodasse sobre nossa plataforma. É a camada
de runtime de agentes."
-->

---

## Slide 4 — Capacidade 1: Isolamento real (90s)

### Não é prompt isolado. É processo isolado.

| Modelo tradicional (chatbot) | Cappy |
|---|---|
| 1 servidor, vários usuários no mesmo processo | 1 container Docker por usuário+conversa |
| Contexto separado por sessão lógica | Filesystem, processo e rede separados |
| Vazamento por bug = vazamento entre clientes | Vazamento por bug = limitado ao container |

**Multi-tenant nativo.** Franquia A não enxerga franquia B nem por acidente
de software — é o kernel garantindo.

> Código: `services/cappycloud_agent/_environment_manager.py`

<!--
Nota de palco — pro executivo:
"Pensem em LGPD, em contratos com franquias diferentes, em dados de cliente
que não podem se misturar. Isolamento por container é o argumento que
fecha com jurídico."
Pro arquiteto:
"Cada conversa tem git worktree próprio. O agente pode clonar repos,
modificar arquivos, rodar comando — sem afetar outra conversa do mesmo
usuário."
-->

---

## Slide 5 — Capacidade 2: Sessão retomável + Human-in-the-Loop (90s)

### O agente pausa, espera o humano, e continua de onde parou.

```
Agente trabalha ──► detecta ação sensível ──► emite ActionRequired
                                                    ↓
                                          stream gRPC pausa
                                                    ↓
                                  frontend mostra "aprovar/negar"
                                                    ↓
                                       usuário responde
                                                    ↓
                                          send_input() retoma
```

- Sessão sobrevive a refresh do browser
- Sobrevive a queda do frontend
- Cleanup automático após `SANDBOX_IDLE_TIMEOUT`

> Código: `services/cappycloud_agent/_grpc_session.py`

<!--
Nota de palco:
"Esse é o mecanismo que viabiliza 'agente faz, humano aprova'. Sem isso,
ou você confia tudo na IA, ou você não usa IA. Cappy resolve o meio-termo
nativamente."
-->

---

## Slide 6 — Capacidade 3: Gateway-agnóstico + Hexagonal (90s)

### Trocar de modelo é mudar uma variável de ambiente.

```env
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
# ou openai/gpt-4o, ou meta-llama/llama-3.1-70b, ...
```

E trocar **qualquer** componente é trocar um adapter:

```
app/ports/         ← interfaces (ABCs)
app/adapters/      ← SQLAlchemy hoje, troca pra outro repo amanhã
                     OpenRouter hoje, troca pra Bedrock amanhã
                     Docker hoje, troca pra Kubernetes amanhã
```

> Documentação: `docs/decisions/adr-001-hexagonal-architecture.md`

<!--
Nota de palco — pro executivo:
"Vendor lock-in zero. Se a Anthropic subir preço, a gente troca pra OpenAI
sem refatorar o código. Se a TOTVS quiser hospedar internamente com Bedrock
ou um modelo on-prem, é um adapter novo, não uma reescrita."
-->

---

## Slide 7 — Caso A: Assistente Release de Notas sobre Cappy (90s)

### O caso "Assistente Protheus Release" implementado sobre nossa plataforma

| Necessidade do caso TOTVS | Como a Cappy resolve |
|---|---|
| Agente treinado em documentação da release | Workspace com docs clonados por conversa |
| Acessível por franquia/cliente-chave | 1 container por franquia — sem vazamento de contexto |
| Atualizar a base sem rebuild | Trocar branch do worktree, sem mexer no agente |
| Suportar múltiplas releases simultâneas | Cada conversa = workspace independente |

> **Diferencial:** o agente não só responde sobre a release — pode **executar**
> consultas, abrir o código da feature, mostrar o diff que introduziu a mudança.

<!--
Nota de palco:
"O Assistente Release que vocês mostraram é texto-em-texto. Sobre a Cappy,
o mesmo agente pode abrir o repositório do Protheus, mostrar o commit que
introduziu a feature, e responder com base no código real, não só na doc."
-->

---

## Slide 8 — Caso B: Produtividade de Implantação sobre Cappy (90s)

### O caso "MITs e aceleradores" com sandbox executável

| Necessidade do caso TOTVS | Como a Cappy resolve |
|---|---|
| Agente que ajuda a criar MITs | Sandbox tem git, node, ferramentas reais |
| Auxílio na criação de aceleradores | Agente pode rodar scaffolding, testar, gerar PR |
| Sem risco de quebrar ambiente do dev | Tudo isolado no container — descarta no fim |
| Histórico do que foi feito | Sessão persistida em PostgreSQL |

> **Diferencial:** agente não sugere código em texto — agente **escreve** o
> arquivo no workspace, **roda** o teste, e mostra o resultado.

<!--
Nota de palco:
"Aqui o diferencial é forte: a iniciativa atual é um chatbot que sugere.
Sobre a Cappy, o agente FAZ — cria o MIT, gera o arquivo, valida sintaxe,
abre o PR. E se errou, descartou o container."
-->

---

## Slide 9 — O que já está pronto (60s)

- Backend FastAPI com arquitetura hexagonal + testes (unit / adapter / integration)
- Agente openclaude empacotado em imagem de sandbox
- Frontend React + Vite + Mantine (login, conversas, streaming em tempo real)
- Orquestração via Docker Compose — sobe com 1 comando
- Persistência dupla: Redis (sessões quentes) + PostgreSQL (histórico)
- Stub gRPC + protobuf versionado em `proto/openclaude.proto`

**Status:** plataforma funcional, rodando, com fluxo end-to-end completo.

<!--
Nota de palco:
"Isso não é PowerPoint-ware. É código rodando. Se quiserem, depois da
sessão eu rodo aqui no meu notebook e mostro uma conversa real."
-->

---

## Slide 10 — Próximo passo (60s)

### O que estamos propondo ao fórum

1. **Piloto** de uma das iniciativas TOTVS rodando sobre Cappy
   - Sugestão: Assistente Release — escopo bem definido, valor visível rápido
2. **Comparativo lado-a-lado** com a implementação atual em 30 dias
   - Métricas: isolamento, custo por sessão, time-to-deploy de nova feature
3. **Decisão informada** sobre adotar Cappy como base das próximas iniciativas

### O que precisamos

- Acesso à base de documentação de uma release (para o piloto)
- 1 arquiteto TOTVS como contraparte técnica
- 30 dias

<!--
Nota de palco — encerramento:
"O fórum hoje mostrou várias iniciativas valiosas. Nossa proposta é não
deixar cada uma reinventar a infra. Cappy está pronta — só precisa de
um piloto pra provar. Obrigado."
-->

---

## Apêndice — Perguntas prováveis e respostas curtas

**"Por que não usar [Dify / LangChain / serviço X]?"**
Cappy é runtime de agente com sandbox isolado por usuário — Dify/LangChain
são frameworks de orquestração de prompt. Camadas diferentes; aliás, dá pra
rodar LangChain *dentro* do nosso sandbox.

**"E custo de container por usuário?"**
TTL de 30 min (configurável). Container vive enquanto a conversa está ativa
e é destruído depois. Em produção, com pool e reaproveitamento, o overhead
é marginal comparado ao custo do LLM.

**"Como integra com SSO da TOTVS?"**
Auth é um adapter (`app/adapters/secondary/`). JWT hoje, SAML/OIDC amanhã —
sem mexer no resto do código.

**"E observabilidade?"**
Logs estruturados por container, sessão rastreável em PostgreSQL, métricas
de gRPC. Pronto pra plugar em Datadog/Grafana/o-que-vocês-usarem.

**"Multi-região?"**
Hexagonal: o `EnvironmentManager` é um adapter. Hoje é Docker local, amanhã
pode ser Kubernetes em região X, Y, Z — mesma interface.
