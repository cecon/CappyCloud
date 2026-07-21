param(
    [string]$FeatureDir = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"

$matrix = Join-Path $FeatureDir "release-impact-matrix.md"
$seed = Join-Path (Split-Path -Parent (Split-Path -Parent $FeatureDir)) "services/sandbox/openclaude-v024-commands.json"
$requiredTerms = @(
    "/model",
    "/ctx",
    "/cost",
    "/doctor",
    "/bughunter",
    "/bughunter-security",
    "/bughunter-perf",
    "/set-context-window",
    "/clear-context-window",
    "/goal",
    "/update",
    "provider",
    "OAuth",
    "repo map",
    "background sessions",
    "production"
)

if (-not (Test-Path $matrix)) {
    throw "Missing release-impact-matrix.md"
}
if (-not (Test-Path $seed)) {
    throw "Missing command catalog seed: $seed"
}

$matrixText = Get-Content -Raw -Path $matrix
$missing = @()
foreach ($term in $requiredTerms) {
    if ($matrixText -notlike "*$term*") {
        $missing += $term
    }
}

$catalog = Get-Content -Raw -Path $seed | ConvertFrom-Json
foreach ($command in $catalog.commands) {
    if ($matrixText -notlike "*$($command.name)*") {
        $missing += $command.name
    }
}

if ($missing.Count -gt 0) {
    throw ("Missing release impact coverage: " + (($missing | Sort-Object -Unique) -join ", "))
}

"Release impact coverage OK: $($catalog.commands.Count) commands and $($requiredTerms.Count) required terms checked."
