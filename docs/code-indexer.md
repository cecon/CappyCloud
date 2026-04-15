# Code Indexer — Documentação Técnica

## O que é

O **Code Indexer** é um serviço interno do CappyCloud que lê o repositório clonado dentro
de um container sandbox e constrói dois índices complementares:

| Índice | Tecnologia | Para que serve |
|--------|-----------|----------------|
| **Semântico** | PostgreSQL + pgvector | Encontrar código *por significado* — "onde trato pagamento QR?" |
| **Grafo AST** | Neo4j | Navegar relações estruturais — "quem chama `processar_pagamento`?" |

Esses índices são consumidos pelo agente IA dentro do container via a ferramenta
`cappy-search`, permitindo que ele responda perguntas sobre o código sem precisar ler
arquivo por arquivo.

---

## Por que existe

Sem indexação, o agente teria de fazer `grep` cego ou ler dezenas de arquivos para
localizar onde uma funcionalidade está implementada. Com o índice:

- Uma pergunta como *"o qrlinx está dando erro no pagamento do PDV"* vira uma busca
  semântica que retorna os 5–10 trechos mais relevantes em menos de 1 segundo.
- O agente vai direto ao ponto — cita arquivo e linha — sem pedir ao usuário que copie
  o stack trace.

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│  cappycloud-code-indexer  (container)                        │
│                                                              │
│  POST /index ──► indexer.py ──► ast_parser.py               │
│                       │              │                       │
│                       │         tree-sitter                  │
│                       │         (Python/JS/TS)               │
│                       │                                      │
│              ┌────────┴──────────┐                           │
│              ▼                   ▼                           │
│         vector_store         graph_store                     │
│         (pgvector)           (Neo4j)                         │
│              │                   │                           │
│    embeddings.py                 │                           │
│  (sentence-transformers)         │                           │
└──────────────┼───────────────────┼───────────────────────────┘
               │                   │
         PostgreSQL              Neo4j
       code_chunks table        grafo AST
```

O indexador **não faz `git clone`**. Ele lê os arquivos direto do container sandbox via
Docker API (`container.get_archive`) — um tar stream sem copiar dados para o host.

---

## Fluxo de indexação passo a passo

### 1. Disparo

Quando um novo ambiente sandbox é criado (ou reiniciado), o `EnvironmentManager`
dispara automaticamente uma requisição `POST /index` para o Code Indexer:

```
EnvironmentManager._trigger_indexing(env_slug)
  └─► POST http://code-indexer:8000/index
        {
          "user_id": "autosystem",       ← env_slug é o namespace
          "container_id": "a2ca5f87...",
          "workspace_path": "/repos/autosystem"
        }
```

A requisição retorna imediatamente (`202 Accepted`) e a indexação roda em background.

### 2. Leitura dos arquivos

`indexer._read_workspace_from_container()` faz:

1. Chama `container.get_archive("/repos/autosystem")` — recebe um tar stream
2. Extrai apenas arquivos com extensões suportadas: `.py`, `.js`, `.ts`, `.tsx`
3. Ignora: `.git/`, `node_modules/`, `__pycache__/`, `dist/`, `migrations/`, etc.
4. Limita a 5.000 arquivos e 500 KB por arquivo

### 3. Parse AST

Para cada arquivo, `ast_parser.parse_file()` usa **tree-sitter** para extrair:

**Chunks** (vão para o pgvector):
- Corpo de cada função/método
- Corpo de cada classe
- Um chunk por arquivo (visão geral)

**Nós do grafo** (vão para o Neo4j):

| Tipo de nó | Representa |
|-----------|-----------|
| `File` | Arquivo de código |
| `Function` | Função top-level |
| `Class` | Definição de classe |
| `Method` | Método dentro de uma classe |
| `Module` | Módulo importado |

**Arestas do grafo**:

| Relação | Significado |
|---------|------------|
| `CONTAINS` | Arquivo contém função/classe |
| `DEFINES` | Classe define método |
| `CALLS` | Função A chama função B |
| `IMPORTS` | Arquivo importa módulo |
| `INHERITS` | Classe herda de outra |

### 4. Geração de embeddings

Os chunks de código são processados em lotes de 64 pelo modelo local
`all-MiniLM-L6-v2` (sentence-transformers, ~80 MB, CPU).

O modelo converte cada trecho de código em um vetor de **384 dimensões** que captura
o *significado* do código — funções que fazem a mesma coisa ficam próximas no espaço
vetorial, mesmo com nomes diferentes.

### 5. Persistência

- **pgvector**: tabela `code_chunks` com embedding + metadados
  (arquivo, linhas, linguagem, tipo de chunk)
- **Neo4j**: grafo com nós e arestas para navegação estrutural

### 6. Conclusão

O status final é registrado em memória:
```json
{
  "status": "ready",
  "progress": 1.0,
  "files_indexed": 4872,
  "error": null
}
```

---

## Como o agente usa o índice — `cappy-search`

O `cappy-search` é um script Bash instalado em `/usr/local/bin/` dentro do container
sandbox. Ele chama o Code Indexer via HTTP e formata a resposta.

O agente tem acesso a 5 comandos:

### `semantic` — busca por significado

```bash
cappy-search semantic "qrlinx erro pagamento pdv"
cappy-search semantic "validação de CPF no cadastro" --limit 5
cappy-search semantic "calculo de desconto" --lang python
```

**Como funciona internamente:**
1. O texto da query é convertido em embedding (mesmo modelo, 384 dims)
2. O banco busca os chunks com menor distância cosseno: `ORDER BY embedding <=> $query`
3. Retorna os N trechos mais similares com arquivo e número de linha

**Quando usar:** ponto de partida para qualquer investigação.

---

### `symbol` — localiza definição pelo nome

```bash
cappy-search symbol ProcessarPagamento --type class
cappy-search symbol calcular_desconto --type function
cappy-search symbol qrlinx
```

**Como funciona:** consulta o Neo4j buscando nós `Function`, `Method` ou `Class`
cujo `.name` contém o texto buscado.

**Quando usar:** quando sabe o nome da classe/função mas não sabe em qual arquivo está.

---

### `refs` — quem usa um símbolo

```bash
cappy-search refs ProcessarPagamento
cappy-search refs calcular_desconto --file fiscal/nfe.py
```

**Como funciona:** consulta arestas `CALLS` ou `IMPORTS` apontando para o símbolo
no grafo Neo4j.

**Quando usar:** para entender o impacto de uma mudança ou rastrear onde uma função
é chamada.

---

### `callgraph` — mapa de chamadas

```bash
cappy-search callgraph ProcessarPagamentoQR --depth 4
```

**Como funciona:** percorre arestas `CALLS` no Neo4j até `depth` níveis,
retornando todos os pares `(caller, callee)` com arquivo e linha.

**Quando usar:** para entender o fluxo completo de execução a partir de um ponto.

---

### `status` — estado da indexação

```bash
cappy-search status
```

Retorna se o índice está `idle` (nunca indexado), `indexing` (em andamento), `ready`
ou `error`.

---

## Quando a indexação é disparada

| Evento | Gatilho |
|--------|---------|
| Novo container criado | `EnvironmentManager._create_env_container()` |
| Container reiniciado após falha | `EnvironmentManager._restart_env_container()` |
| Indexação manual (admin) | `POST http://localhost:38090/index` |
| Forçar reindexação | `POST /index` com `"force": true` |

**Nota:** a indexação é sempre incremental por `user_id` (= `env_slug`). Ao reindexar,
os dados antigos são apagados e substituídos.

---

## Namespacing por ambiente

Cada ambiente sandbox tem seu próprio namespace isolado no índice identificado pelo
`env_slug` (ex: `autosystem`). Isso significa:

- O ambiente `autosystem` só busca no código do repositório `autosystem`
- O ambiente `meuoutroprojeto` tem índice separado
- Dentro do container, `CAPPY_USER_ID=autosystem` garante que `cappy-search` consulte
  o índice correto

---

## Limitações conhecidas

| Limitação | Detalhe |
|-----------|---------|
| **Linguagens suportadas** | Python, JavaScript, TypeScript/TSX apenas |
| **Arquivos excluídos** | Binários, migrações, `node_modules`, `.git` |
| **Tamanho máximo** | 500 KB por arquivo, 5.000 arquivos por repositório |
| **Chamadas dinâmicas** | `getattr(obj, método)()` não é detectado no grafo |
| **Estado em memória** | Status de indexação reinicia com o container do code-indexer |
| **Embeddings CPU-only** | Indexação de 5.000 arquivos leva ~10–15 min na primeira vez |

---

## Troubleshooting

### `cappy-search status` retorna `idle`

O repositório nunca foi indexado. Disparar manualmente:

```powershell
$id = docker inspect cappy_env_SLUG --format "{{.Id}}"
$body = '{"user_id":"SLUG","container_id":"' + $id + '","workspace_path":"/repos/SLUG"}'
Invoke-RestMethod -Uri "http://localhost:38090/index" -Method POST `
  -ContentType "application/json" -Body $body
```

### `cappy-search` retorna erro `CAPPY_USER_ID não definido`

O container foi criado antes da correção do `CAPPY_USER_ID`. Recriar o ambiente pela
UI ou via `POST /environments/{id}/wake`.

### Code Indexer não sobe — `unknown type: public.vector`

A extensão pgvector não está ativada no banco:

```bash
docker exec cappycloud-postgres psql -U cappy -d cappycloud \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"
docker restart cappycloud-code-indexer
```

### Resultados semânticos ruins / irrelevantes

O índice pode estar desatualizado após um `git pull` no container. Forçar reindexação:

```powershell
# Adicionar "force": true ao body
$body = '{"user_id":"SLUG","container_id":"ID","workspace_path":"/repos/SLUG","force":true}'
Invoke-RestMethod -Uri "http://localhost:38090/index" -Method POST `
  -ContentType "application/json" -Body $body
```

---

## Referência rápida de endpoints

| Método | Path | Descrição |
|--------|------|-----------|
| `POST` | `/index` | Dispara indexação (async, retorna 202) |
| `GET` | `/index/{user_id}` | Status da indexação |
| `POST` | `/search/semantic` | Busca por similaridade semântica |
| `POST` | `/search/symbol` | Localiza símbolo pelo nome no grafo |
| `POST` | `/search/references` | Quem chama/importa um símbolo |
| `POST` | `/search/callgraph` | Grafo de chamadas a partir de uma função |
| `GET` | `/health` | Health check |

Porta exposta no host: **38090** (`http://localhost:38090`).
