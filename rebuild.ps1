# ──────────────────────────────────────────────────────────────
# CappyCloud — Rebuild completo após mudanças
# Execute no PowerShell:
#   cd d:\projetos\CappyCloud
#   .\rebuild.ps1
# ──────────────────────────────────────────────────────────────
Set-Location $PSScriptRoot

function Write-Step { param($msg) Write-Host "`n==> $msg" -ForegroundColor Cyan }

Write-Step "1/3 — Rebuild sandbox (adiciona ripgrep + corrige variáveis)..."
docker build -t cappycloud-sandbox:latest .\services\sandbox\
if ($LASTEXITCODE -ne 0) { Write-Error "Sandbox build falhou"; exit 1 }

Write-Step "2/3 — Rebuild pipelines (lógica de repo URL + recreação de sandbox)..."
docker compose build pipelines
if ($LASTEXITCODE -ne 0) { Write-Error "Pipelines build falhou"; exit 1 }

Write-Step "3/3 — Reiniciando serviço pipelines..."
docker compose up -d pipelines
Start-Sleep 8
docker compose logs pipelines --tail=10

Write-Host "`n==> Pronto! Acesse http://localhost:38080" -ForegroundColor Green
Write-Host "    Envie a URL do repo na primeira mensagem do chat." -ForegroundColor Green
