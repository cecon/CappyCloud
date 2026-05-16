# CappyCloud

**CappyCloud e uma plataforma de agentes tecnicos para times que precisam investigar codigo, documentacao e operacao sem depender de um ambiente fixo ou de um unico repositorio.**

Ela combina chat com agente, sandbox Docker, worktrees Git transitorios, skills por repositorio, conectores MCP e modelos via OpenRouter para entregar respostas tecnicas com evidencia: arquivo, linha, documentacao consultada, comando executado e custo da execucao.

O ponto central do produto e simples: **o contexto muda de cliente para cliente, de squad para squad e de demonstracao para demonstracao**. O CappyCloud trata repositorios como contexto de trabalho provisionado para uma conversa, nao como infraestrutura permanente acoplada ao deploy.

---

## Por Que Existe

Times tecnicos perdem tempo repetindo o mesmo ciclo:

- localizar o repositorio certo;
- entender regras de negocio espalhadas entre codigo, XMLs, docs internas e Confluence;
- descobrir qual modelo de LLM responde melhor;
- justificar a resposta com evidencias;
- medir custo real de tokens;
- preparar uma demonstracao convincente sem montar tudo manualmente.

O CappyCloud transforma esse ciclo em uma experiencia unica: abrir uma conversa, selecionar os repositorios relevantes, acionar o agente e receber uma resposta auditavel.

---

## O Que Ele Entrega

- **Chat tecnico com streaming**: resposta em tempo real, eventos de ferramenta, historico e custo por mensagem.
- **Repositorios transitorios por conversa**: cada conversa recebe uma sessao em `/repos/sessions/<session_id>/...`, com worktrees preparados conforme os repos selecionados.
- **Skills por repositorio**: instrucoes especializadas sao cadastradas no banco e carregadas conforme o repositorio da sessao, evitando depender de skills globais ou conhecimento implicito.
- **MCP e ferramentas dinamicas**: conectores podem ser enviados ao sandbox antes de cada execucao, permitindo integrar documentacao, observabilidade e sistemas internos.
- **OpenRouter com precos atualizados**: modelos cadastrados no ambiente podem ser sincronizados com a API publica do OpenRouter; o custo usa tokens reais e tabela de preco atual.
- **Sandbox isolado do host**: o agente roda dentro do container `cappycloud-sandbox`, com API FastAPI, PostgreSQL e Redis coordenando sessoes e historico.
- **Evidencia tecnica**: o fluxo foi desenhado para respostas que citam codigo, arquivos, linhas, documentos e URLs reais quando disponiveis.

---

## Realidade Dos Ambientes

Este projeto nao assume que os repositorios sao os mesmos em todos os ambientes.

Em uma instalacao, voce pode ter repositorios de produto, servicos internos e documentacao corporativa. Em outra, pode haver outros repos, outras skills, outros MCPs, outro provedor de observabilidade e outro conjunto de modelos liberados.

Por isso:

- repositorios cadastrados no banco sao **catalogo do ambiente**, nao parte fixa do codigo;
- uma conversa referencia um ou mais repositorios desse catalogo;
- o sandbox materializa worktrees em uma sessao transitoria;
- a sessao pode ser descartada apos inatividade sem perder o historico da conversa;
- skills, MCPs e precos de LLM devem ser carregados do ambiente atual.

Essa abordagem deixa o CappyCloud adequado para demonstracoes, consultoria, suporte tecnico, squads internas e ambientes de cliente onde o contexto muda com frequencia.

---

## Arquitetura

```text
Browser
  -> React + Vite + Mantine
      -> FastAPI
          -> PostgreSQL
              users, repositorios, skills, conversas, mensagens, custos
          -> Redis
              cache e TTL de sessoes
          -> cappycloud-sandbox
              /repos/sessions/<session_id>/<repo-alias>
              openclaude gRPC
              ferramentas Bash/Grep/Read/MCP
                  -> OpenRouter
                  -> APIs internas/publicas configuradas
```

Na pratica, o sandbox e um runtime controlado. As conversas criam sessoes dentro dele; os repositorios entram e saem conforme a necessidade da conversa.

---

## Stack

- **Frontend**: React, Vite, Mantine
- **Backend**: FastAPI, JWT, SQLAlchemy, asyncpg
- **Agente**: OpenClaude via gRPC
- **Runtime**: Docker sandbox
- **Modelos**: OpenRouter, com selecao dinamica por conversa
- **Persistencia**: PostgreSQL
- **Sessao/cache**: Redis
- **Ferramentas**: Bash, Grep, Read, MCP servers, endpoints internos do sandbox

---

## Fluxo De Uma Conversa

1. Usuario cria ou abre uma conversa.
2. Seleciona os repositorios relevantes para aquele caso.
3. A API prepara uma sessao no sandbox.
4. O sandbox cria worktrees em `/repos/sessions/<session_id>/`.
5. O contexto do agente e montado com:
   - mensagem do usuario;
   - repositorios da conversa;
   - skills ativas daqueles repositorios;
   - MCPs ativos do usuario;
   - configuracoes de modelo.
6. O agente investiga usando codigo, ferramentas e documentacao disponivel.
7. A resposta volta por streaming.
8. Tokens, modelo e custo sao persistidos para auditoria.

---

## Quick Start

### 1. Clone

```bash
git clone https://github.com/yourorg/cappycloud.git
cd cappycloud
```

### 2. Configure o ambiente

```bash
cp .env.example .env
```

Defina pelo menos:

| Variavel | Uso |
|---|---|
| `OPENROUTER_API_KEY` | Chave para execucao dos modelos |
| `POSTGRES_PASSWORD` | Senha do PostgreSQL |
| `JWT_SECRET` | Segredo para assinatura JWT |
| `WEB_PORT` | Porta da UI, padrao `38081` |
| `API_PORT` | Porta da API, padrao `38000` |

### 3. Suba a stack

```bash
docker compose up -d --build
```

Servicos principais:

| Servico | Host | Observacao |
|---|---:|---|
| Web | `http://localhost:38081` | UI do produto |
| API | `http://localhost:38000` | FastAPI |
| PostgreSQL | `localhost:15432` | Debug/local |
| Redis | `localhost:16379` | Debug/local |
| Sandbox | interno | Runtime do agente |

### 4. Primeiro uso

1. Abra `http://localhost:38081`.
2. Crie uma conta.
3. Cadastre ou selecione um repositorio do ambiente.
4. Crie uma conversa.
5. Envie uma pergunta tecnica.

Exemplo:

```text
Analise o repositorio selecionado e explique onde a regra de bloqueio de venda e aplicada. Cite arquivos e linhas.
```

---

## Modelos E Custos

O CappyCloud usa OpenRouter como gateway de modelos. O modelo pode ser escolhido por conversa, e o custo salvo usa:

- tokens reais retornados pelo provedor;
- tokens de cache quando o provedor reporta `cache_read` ou equivalente;
- preco atualizado a partir do catalogo publico do OpenRouter para os modelos cadastrados no ambiente.

Isso evita tratar modelos pagos como gratuitos e evita custo baseado em estimativa local.

---

## Skills Por Repositorio

Skills sao parte do contexto do ambiente.

Em vez de depender de uma skill global que tenta servir para tudo, cada repositorio pode ter skills proprias:

- regras de negocio conhecidas;
- caminhos importantes;
- documentacao de banco;
- padroes de investigacao;
- fontes externas obrigatorias;
- formato esperado de resposta.

Quando uma conversa seleciona um repositorio, suas skills ativas sao carregadas no prompt do agente.

---

## Comandos Uteis

```bash
# Ver status da stack
docker compose ps

# Logs da API
docker compose logs -f api

# Logs do sandbox
docker compose logs -f sandbox

# Rebuild de API e sandbox
docker compose up -d --build --force-recreate api sandbox

# Derrubar a stack
docker compose down

# Derrubar e apagar volumes locais
docker compose down -v
```

---

## Estrutura Do Projeto

```text
cappycloud/
|-- docker-compose.yml
|-- proto/
|   `-- openclaude.proto
|-- services/
|   |-- api/                  # FastAPI, auth, repos, skills, conversas
|   |-- cappycloud_agent/     # Pipeline do agente, sessoes, custos, contexto
|   `-- sandbox/              # Runtime Docker com openclaude e ferramentas
|-- web/                      # React + Vite + Mantine
|-- docs/
`-- README.md
```

---

## Troubleshooting

### A conversa nao encontra o repositorio

Confirme se o repositorio esta cadastrado no ambiente e se a conversa foi criada com ele selecionado. Os worktrees sao transitorios; nao assuma que um repo visto em outra conversa existe na sessao atual.

### O custo veio zerado

Verifique:

- se o modelo existe em `ai_models`;
- se o provider aponta para OpenRouter;
- se a API conseguiu consultar `https://openrouter.ai/api/v1/models`;
- se o provedor retornou usage no stream.

### O agente nao responde

```bash
docker compose logs api
docker compose logs sandbox
```

Verifique tambem `OPENROUTER_API_KEY`, modelo selecionado e conectividade do sandbox.

---

## Posicionamento

CappyCloud nao e apenas um chat com codigo. Ele e um **ambiente tecnico sob demanda** para demonstrar, investigar e resolver problemas reais com rastreabilidade.

Ele funciona melhor quando cada instalacao assume sua propria realidade: seus repositorios, suas skills, seus conectores, seus modelos e suas fontes de documentacao.
