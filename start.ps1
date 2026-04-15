# ──────────────────────────────────────────────────────────────

# CappyCloud — Script de inicialização

# Execute no PowerShell como Administrador (ou normal se Docker

# Desktop estiver configurado para o seu usuário):

#

#   cd d:\projetos\CappyCloud

#   .\start.ps1

# ──────────────────────────────────────────────────────────────

Set-Location $PSScriptRoot

$ErrorActionPreference = "Stop"



function Write-Step { param($msg) Write-Host "`n==> $msg" -ForegroundColor Cyan }

function Write-OK   { param($msg) Write-Host "    OK: $msg" -ForegroundColor Green }

function Write-Warn { param($msg) Write-Host "    AVISO: $msg" -ForegroundColor Yellow }



# ── 1. Pré-requisitos ─────────────────────────────────────────

Write-Step "Verificando Docker..."

docker info > $null 2>&1

if ($LASTEXITCODE -ne 0) {

    Write-Error "Docker não está rodando. Abra o Docker Desktop e tente novamente."

    exit 1

}

Write-OK "Docker está rodando."



# ── 2. Verificar .env ─────────────────────────────────────────

Write-Step "Verificando .env..."

if (-not (Test-Path ".env")) {

    Write-Error "Arquivo .env não encontrado. Copie .env.example para .env e preencha os valores."

    exit 1

}

$envContent = Get-Content ".env" -Raw

if ($envContent -match "OPENROUTER_API_KEY=sk-or-v1-") {

    Write-OK "OPENROUTER_API_KEY configurada."

} else {

    Write-Warn "OPENROUTER_API_KEY parece não estar configurada corretamente."

}



# ── 3. Build da imagem sandbox ────────────────────────────────

Write-Step "Verificando imagem sandbox (cappycloud-sandbox:latest)..."

$sandboxExists = docker images cappycloud-sandbox:latest --format "{{.Repository}}" 2>$null

if ($sandboxExists -eq "cappycloud-sandbox") {

    Write-OK "Imagem sandbox já existe — pulando build."

} else {

    Write-Host "    Buildando imagem sandbox (clona + compila openclaude ~3-5min)..." -ForegroundColor Yellow

    docker build -t cappycloud-sandbox:latest .\services\sandbox\

    if ($LASTEXITCODE -ne 0) {

        Write-Error "Falha no build da imagem sandbox."

        exit 1

    }

    Write-OK "Imagem sandbox criada."

}



# ── 4. Criar a rede Docker se não existir ─────────────────────

Write-Step "Verificando rede Docker cappycloud_net..."

$netExists = docker network ls --filter name=cappycloud_net --format "{{.Name}}" 2>$null

if ($netExists -eq "cappycloud_net") {

    Write-OK "Rede cappycloud_net já existe."

} else {

    docker network create cappycloud_net

    Write-OK "Rede cappycloud_net criada."

}



# ── 5. Subir o stack ──────────────────────────────────────────

Write-Step "Buildando e subindo o stack (postgres, redis, pipelines, LibreChat, MongoDB, ...)..."

docker compose up -d --build

if ($LASTEXITCODE -ne 0) {

    Write-Error "Falha ao subir o stack."

    exit 1

}

Write-OK "Stack iniciado."



# ── 6. Aguardar serviços ficarem saudáveis ────────────────────

Write-Step "Aguardando serviços ficarem prontos (até 60s)..."

$timeout = 60

$elapsed = 0

do {

    Start-Sleep -Seconds 5

    $elapsed += 5

    $status = docker compose ps --format json 2>$null | ConvertFrom-Json

    $unhealthy = $status | Where-Object { $_.Health -eq "unhealthy" -or $_.State -ne "running" }

    if ($unhealthy) {

        Write-Host "    Aguardando: $($unhealthy.Service -join ', ')..." -ForegroundColor DarkGray

    }

} while ($unhealthy -and $elapsed -lt $timeout)



# ── 7. URL final ───────────────────────────────────────────────

$port = "38080"

if ($envContent -match "LIBRECHAT_PORT=(\d+)") {

    $port = $Matches[1]

}



# ── 8. Status final ───────────────────────────────────────────

Write-Step "Status dos containers:"

docker compose ps



Write-Host ""

Write-Host "──────────────────────────────────────────────────────" -ForegroundColor Green

Write-Host "  CappyCloud no ar!" -ForegroundColor Green

Write-Host "  Acesse: http://localhost:$port" -ForegroundColor Green

Write-Host "  (Registre-se, depois endpoint CappyCloud → CappyCloud Agent)" -ForegroundColor Green

Write-Host "──────────────────────────────────────────────────────" -ForegroundColor Green

Write-Host ""

Write-Host "  Logs ao vivo:  docker compose logs -f" -ForegroundColor DarkGray

Write-Host "  Parar tudo:    docker compose down" -ForegroundColor DarkGray

Write-Host ""

