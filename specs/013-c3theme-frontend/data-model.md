# Data Model: inventário de telas

Não há dados persistidos novos. A entidade desta feature é a **tela portada**:
rota do `web/`, tela equivalente no `web-c3/`, quem acessa e estado.

Estados: `pendente` → `em andamento` → `paridade` (checklist da tela aprovado).

| # | Rota `web/` | Página atual | Acesso | História | Estado |
|---|---|---|---|---|---|
| 1 | `/login` | `LoginPage` | aberto | US1 | paridade |
| 2 | `/change-password` | `ChangePasswordPage` | logado | US1 | paridade |
| 3 | `/chat` | `ChatPage` | logado | US2 | pendente |
| 4 | `/skills` | `SkillsPage` | logado | US3 | pendente |
| 5 | `/runs` | `RunsPage` | logado | US3 | pendente |
| 6 | `/mcp` | `McpServerPage` | logado | US3 | pendente |
| 7 | `/analytics` | `AnalyticsPage` | logado | US3 | pendente |
| 8 | `/settings` | `SettingsPage` | super admin | US3 | pendente |
| 9 | `/admin` | `AdminDashboardPage` | admin | US4 | pendente |
| 10 | `/admin/conversations` | `AdminConversationsPage` | admin | US4 | pendente |
| 11 | `/admin/reports` | `AdminReportsPage` | admin | US4 | pendente |
| 12 | `/admin/reports/print` | `AdminReportPrintPage` | admin (impressão) | US4 | pendente |
| 13 | `/admin/users` | `AdminUsersPage` | admin | US4 | pendente |
| 14 | `/admin/sandboxes` | `AdminSandboxesPage` | admin | US4 | pendente |
| 15 | `/admin/models` | `AdminModelsPage` | admin | US4 | pendente |
| 16 | `/admin/providers` | `AdminProvidersPage` | admin | US4 | pendente |
| 17 | `/admin/workspaces` | `AdminWorkspacesPage` | super admin | US4 | pendente |
| 18 | `/admin/repositories` | `AdminRepositoriesPage` | super admin | US4 | pendente |
| 19 | `/admin/skills-global` | `AdminGlobalSkillsPage` | super admin | US4 | pendente |

Redirecionamentos a manter: `/` e `*` → `/chat`; `/register` → `/login`; `/environments` → `/`; `/admin/agents-global` → `/admin/sandboxes`.

## Checklist de paridade (por tela)

- Mesmas ações disponíveis, com o mesmo resultado na API.
- Mesmos estados: carregando, vazio, erro (mensagem em português) e sucesso.
- Mesma regra de acesso (menu e acesso direto pelo endereço).
- Utilizável em tela estreita.
- Textos em pt-BR, sem placeholder do tema.
- Conferido lado a lado com a tela do `web/` por quem conhece a tela.
