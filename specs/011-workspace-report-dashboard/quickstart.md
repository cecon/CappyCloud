# Quickstart: Relatório de uso por workspace

## Validar a API

```bash
cd services/api
pytest tests/integration/test_api_admin_reports.py tests/unit/test_report_themes.py tests/unit/test_workspace_report_metrics.py -q --no-cov
```

## Validar na tela

1. Subir API e web (`docker-compose.dev.yml` ou `start.ps1`).
2. Entrar como admin e abrir **Admin → Relatórios** (`/admin/reports`).
3. Escolher o workspace, um atalho de período (7/15/30/90 dias) e, se quiser,
   a branch.
4. Conferir consultas, analistas, custo total e médias, a tabela por analista,
   as semanas e os temas.
5. **Exportar XLSX** e **CSV**: os totais batem com a tela.
6. **Versão para impressão**: abre em outra aba; "Imprimir / salvar PDF" usa o
   diálogo do navegador. Filtros e botões não saem no papel.
7. Super admin: **Temas** → escolher modelo ou editar o JSON → Salvar; o
   relatório recalcula.
8. Admin comum sem acesso a um workspace: ele não aparece na lista; chamar a API
   com o id dele devolve 403.
