# Contrato: /api/admin/reports

Todas as rotas exigem papel admin (403 para usuário comum). Admin comum só
enxerga workspaces de `user_workspace_access`; super admin enxerga todos.

## GET /admin/reports/options

Query: `workspace_id` (opcional).

200:

```json
{
  "workspaces": [{ "id": "…", "slug": "proteus", "name": "PROTEUS" }],
  "branches": ["main", "master"],
  "can_edit_themes": true
}
```

403 se `workspace_id` não for visível; 404 se não existir.

## GET /admin/reports/workspace

Query: `workspace_id` (opcional, ausente = todos visíveis), `branch`
(opcional), `start`, `end` (`YYYY-MM-DD`, inclusivas, fuso America/Sao_Paulo;
padrão: últimos 30 dias até hoje).

200: relatório descrito em [data-model.md](../data-model.md) (inclui `brl`,
a cotação PTAX usada para os valores em R$, ou `null`), mais
`generated_at`, `filters` (`workspace_id`, `workspace_name`, `branch`, `start`,
`end`, `timezone`, `currency` = `USD`).

403 workspace não visível; 404 workspace inexistente; 422 `start > end` ou
período > 366 dias.

## GET /admin/reports/workspace/export

Mesma query do relatório + `format` = `xlsx` (padrão) ou `csv`.
Devolve o arquivo com `Content-Disposition: attachment; filename=relatorio-<slug|todos>-<start>-<end>.<ext>`.
Mesmos erros do relatório.

## GET /admin/reports/themes/{workspace_id}

200:

```json
{
  "workspace_id": "…",
  "preset": "protheus-tss",
  "custom": false,
  "rules": [{ "key": "…", "label": "…", "patterns": ["…"] }],
  "presets": [{ "key": "generico", "label": "Genérico" }]
}
```

`rules` são as regras em vigor. 403/404 como acima.

## PUT /admin/reports/themes/{workspace_id}

Só super admin (403 para os demais). Corpo:

```json
{ "preset": "protheus-tss", "rules": null }
```

- `rules` preenchido: grava regras próprias (validadas; 422 se inválidas).
- `rules` nulo: apaga as regras próprias e usa `preset` (nulo = `generico`;
  modelo desconhecido = 422).

200: mesmo corpo do GET.
