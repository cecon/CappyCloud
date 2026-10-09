# Data Model: Relatório de uso por workspace

## Mudança no banco

`workspaces` ganha:

| Coluna | Tipo | Nulo | Uso |
|--------|------|------|-----|
| `report_theme_preset` | varchar(64) | sim | nome do modelo pronto (`generico`, `nfse-protheus`) |
| `report_themes` | jsonb | sim | regras próprias; quando preenchida, vale sobre o modelo |

Migration: adiciona as colunas e faz
`UPDATE workspaces SET report_theme_preset = 'nfse-protheus' WHERE slug = 'proteus'`.

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

- `totals`: `consultations`, `analysts`, `messages`, `cost_usd`,
  `avg_cost_per_consultation`, `avg_cost_per_analyst`.
- `analysts[]`: `email`, `label` (parte antes do @), `consultations`,
  `cost_usd`, `avg_cost_usd`.
- `weeks[]`: `week` (`2026-W40`), `start` (segunda-feira), `consultations`,
  `cost_usd` — todas as semanas que tocam o período.
- `themes[]`: `key`, `label`, `consultations`, `cost_usd` ("Outros" por último).
- `workspaces[]`: `id`, `slug`, `name`, `consultations`, `cost_usd`.
- `consultations[]`: `conversation_id`, `workspace_slug`, `analyst_email`,
  `ticket_number`, `title`, `theme_key`, `theme_label`, `branches`,
  `messages`, `cost_usd`, `first_message_at`, `last_message_at`.
