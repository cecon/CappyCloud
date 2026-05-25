# MCP Telemetry

Obs.1 registra uma linha sanitizada por chamada de tool MCP para orientar o roadmap
GraphRAG com dados reais de uso. A implementação é agnóstica a repositório: cada
linha referencia o `repository_id` vinculado ao `user_mcp_servers` que recebeu a
chamada.

## Tabela

`mcp_tool_invocations` guarda:

- `trace_id`: UUID da requisição MCP. Vem de `X-Request-Id`,
  `X-Correlation-Id` ou é gerado pela API.
- `server_id`, `user_id`, `repo_id`: vínculos do MCP. FKs usam
  `ON DELETE SET NULL` para preservar histórico.
- `tool_name`: nome canônico da tool executada, por exemplo
  `repository_graph`. Aliases entram em `metadata.requested_tool_name`.
- `arguments_sanitized`: argumentos sem campos sensíveis.
- `status`: `ok`, `error` ou `timeout`.
- `duration_ms`, `response_bytes`, `response_hash`.
- `materialized`: preenchido apenas para `repository_graph`.
- `caller_user_agent` e `caller_session_id`.
- `metadata`: extensão JSONB para campos futuros.

## Sanitização

Não armazenamos headers, bearer tokens, resposta completa, conteúdo de arquivos ou
conteúdo de chunks. Argumentos são copiados e sanitizados antes do insert.

Campos com estas chaves são substituídos por `<redacted>`:

`token`, `password`, `secret`, `key`, `bearer`, `authorization`, `apikey`,
`api_key`, `auth`, `credential`, `credentials`, `cookie`.

Strings acima de 500 caracteres são truncadas. Listas são limitadas a 50 itens.
Objetos aninhados são limitados a profundidade 4.

`response_bytes` e `response_hash` são calculados sobre o JSON retornado pela
tool dentro do protocolo MCP. O hash usa apenas os primeiros 4 KB para detectar
respostas repetidas sem guardar o corpo.

## Endpoint Admin

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "https://app.cappyfy.com/api/admin/mcp/telemetry?from=2026-05-01T00:00:00Z&to=2026-05-25T23:59:59Z"
```

Filtros opcionais:

- `repo_id`
- `tool_name`

A janela é obrigatória e limitada a 90 dias. A resposta traz totais, uso por
tool, uso por repo, tools nunca usadas e principais erros.

## Retenção

`MCP_TELEMETRY_RETENTION_DAYS` controla a retenção, com padrão de 180 dias. Um
job diário remove linhas mais antigas. Esta fase não agrega nem arquiva dados
removidos.

## Trace ID

Callers podem enviar `X-Request-Id` ou `X-Correlation-Id` como UUID. A API ecoa o
valor em `X-Request-Id`. Se o header vier ausente ou inválido, a API gera um UUID
novo.

`Mcp-Session-Id` é opcional e armazenado truncado a 200 caracteres para separar
clientes como Claude, Cursor ou Claude Code quando eles enviarem esse contexto.
