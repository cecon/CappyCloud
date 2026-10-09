# Data Model: Relatório de uso por workspace

## Mudança no banco

`workspaces` ganha:

| Coluna | Tipo | Nulo | Uso |
|--------|------|------|-----|
| `report_theme_preset` | varchar(64) | sim | nome do modelo pronto (`generico`, `protheus-tss`, `nfse-detalhado`, `por-assunto`) |
| `report_themes` | jsonb | sim | regras próprias; quando preenchida, vale sobre o modelo |

Migration: adiciona as colunas e faz
`UPDATE workspaces SET report_theme_preset = 'protheus-tss' WHERE slug = 'proteus'`.

## Regra de tema (JSON)

```json
{ "key": "nfse-retencoes", "label": "NFS-e: Retenções e ISS", "patterns": ["retenc", "\\biss\\b"] }
```

- `key`: `^[a-z0-9][a-z0-9-]{0,47}$`, única, diferente de `outros`.
- `label`: 1–80 caracteres.
- `patterns`: 1–30 regex de até 200 caracteres, que compilam.
- Lista: 1–30 regras. Ordem importa (primeira que casar vence).

## Entidades lidas (port)

- `ReportWorkspace`: `id`, `slug`, `name`, `theme_preset`, `theme_rules`.
- `ReportMessage`: `conversation_id`, `created_at` (UTC), `cost_usd`.
- `ReportConversation`: `id`, `workspace_id`, `user_email`, `title`,
  `ticket_number`, `branches` (conjunto de `base_branch` / `branch_name`),
  `first_user_message`.

## Relatório (saída)

- `brl`: `rate`, `quoted_on`, `source` (PTAX venda) ou `null`.
- `totals`: `questions` (consultas), `conversations`, `analysts`, `messages`,
  `cost_usd`, `avg_cost_per_question`, `avg_cost_per_conversation`,
  `avg_cost_per_analyst`.
- `analysts[]`: `email`, `label` (parte antes do @), `questions`,
  `conversations`, `cost_usd`, `avg_cost_per_question`.
- `weeks[]`: `start`, `end`, `label` (`01-07/09`), `questions`,
  `conversations`, `cost_usd` — blocos de 7 dias a partir de `start`.
- `themes[]`: `key`, `label`, `questions`, `conversations`, `cost_usd`,
  `share` (fração das perguntas; "Outros" por último).
- `workspaces[]`: `id`, `slug`, `name`, `questions`, `conversations`, `cost_usd`.
- `conversations[]`: `conversation_id`, `workspace_slug`, `analyst_email`,
  `ticket_number`, `title`, `theme_key`, `theme_label`, `branches`,
  `questions`, `messages`, `cost_usd`, `first_message_at`, `last_message_at`.
