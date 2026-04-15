# ──────────────────────────────────────────────────────────────
# CappyCloud — Branding para LibreChat
#
# Não montamos pasta em /app/client/public/images (isso apagaria os
# assets do frontend e quebraria a UI). Use:
#   - APP_TITLE no .env
#   - interface.customWelcome em librechat.yaml
#   - Painel Admin do LibreChat para logo/favicon, se disponível
#   - iconURL no endpoint custom em librechat.yaml (URL pública da imagem)
#
# Uso:
#   cd d:\projetos\CappyCloud
#   .\set_branding.ps1
# ──────────────────────────────────────────────────────────────
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "  Branding LibreChat (sem sobrescrever public/images):" -ForegroundColor Cyan
Write-Host "  - Edite APP_TITLE em .env" -ForegroundColor DarkGray
Write-Host "  - Edite interface.customWelcome em librechat.yaml" -ForegroundColor DarkGray
Write-Host "  - Opcional: iconURL no endpoint CappyCloud em librechat.yaml (URL HTTPS)" -ForegroundColor DarkGray
Write-Host ""
