# MCP Telemetry

Obs.1 registra uma linha sanitizada por chamada de tool MCP para orientar o
roadmap com dados reais de uso. A implementacao e agnostica a repositorio: cada
linha referencia o `repository_id` vinculado ao `user_mcp_servers` que recebeu a
chamada.

## Tabela

`mcp_tool_invocations` guarda:

- `trace_id`: UUID da requisicao MCP. Vem de `X-Request-Id`,
  `X-Correlation-Id` ou e gerado pela API.
- `server_id`, `user_id`, `repo_id`: vinculos do MCP. FKs usam
  `ON DELETE SET NULL` para preservar historico.
- `tool_name`: nome canonico da tool executada, por exemplo
  `repository_search`. Aliases entram em `metadata.requested_tool_name`.
- `arguments_sanitized`: argumentos sem campos sensiveis.
- `status`: `ok`, `error` ou `timeout`.
- `duration_ms`, `response_bytes`, `response_hash`.
- `caller_user_agent` e `caller_session_id`.
- `metadata`: extensao JSONB para campos futuros.

## Sanitizacao

Nao armazenamos headers, bearer tokens, resposta completa, conteudo de arquivos
ou conteudo de chunks. Argumentos sao copiados e sanitizados antes do insert.

Campos com estas chaves sao substituidos por `<redacted>`:

`token`, `password`, `secret`, `key`, `bearer`, `authorization`, `apikey`,
`api_key`, `auth`, `credential`, `credentials`, `cookie`.

Strings acima de 500 caracteres sao truncadas. Listas sao limitadas a 50 itens.
Objetos aninhados sao limitados a profundidade 4.

`response_bytes` e `response_hash` sao calculados sobre o JSON retornado pela
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

A janela e obrigatoria e limitada a 90 dias. A resposta traz totais, uso por
tool, uso por repo, tools nunca usadas e principais erros.

## Retencao

`MCP_TELEMETRY_RETENTION_DAYS` controla a retencao, com padrao de 180 dias. Um
job diario remove linhas mais antigas. Esta fase nao agrega nem arquiva dados
removidos.

## Trace ID

Callers podem enviar `X-Request-Id` ou `X-Correlation-Id` como UUID. A API ecoa o
valor em `X-Request-Id`. Se o header vier ausente ou invalido, a API gera um UUID
novo.

`Mcp-Session-Id` e opcional e armazenado truncado a 200 caracteres para separar
clientes como Claude, Cursor ou Claude Code quando eles enviarem esse contexto.
