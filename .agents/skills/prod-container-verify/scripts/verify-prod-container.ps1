param(
  [string]$HostName = "191.235.116.32",
  [int]$Port = 2499,
  [string]$User = "mpc-ai-user",
  [string]$KeyFile = "F:\OneDriver\OneDrive\C3CON\Servers\LinxN8N.ppk",
  [string]$CredentialFile = "$HOME\.ssh\cappy-prod.password.clixml",
  [string]$BitviseSexec = "C:\Program Files (x86)\Bitvise SSH Client\sexec.exe"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $BitviseSexec)) {
  throw "Bitvise sexec not found: $BitviseSexec"
}
if (-not (Test-Path $KeyFile)) {
  throw "Production key file not found: $KeyFile"
}
if (-not (Test-Path $CredentialFile)) {
  throw "Credential file not found: $CredentialFile"
}

$cmdFile = Join-Path $env:TEMP "cappy-prod-verify-$([guid]::NewGuid()).txt"
@'
echo --- host
hostname
echo --- user
whoami
echo --- services
sudo -n docker service ls --format "{{.Name}} {{.Image}} {{.Replicas}}" | grep -i cappy || true
echo --- containers
sudo -n docker ps --format "{{.ID}} {{.Names}} {{.Image}} {{.Status}}" | grep -i cappy || true
echo --- sandbox inspect
sudo -n docker inspect $(sudo -n docker ps --format "{{.ID}} {{.Names}}" | grep cappycloud_sandbox | awk "{print \$1; exit}") --format "name={{.Name}} image={{.Config.Image}} image_id={{.Image}} status={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{end}} started={{.State.StartedAt}}"
echo --- openclaude_version
sudo -n docker exec $(sudo -n docker ps --format "{{.ID}} {{.Names}}" | grep cappycloud_sandbox | awk "{print \$1; exit}") node /openclaude/dist/cli.mjs --version
echo --- runtime_status
sudo -n docker exec $(sudo -n docker ps --format "{{.ID}} {{.Names}}" | grep cappycloud_sandbox | awk "{print \$1; exit}") curl -fsS http://127.0.0.1:8080/runtime/status
'@ | Set-Content -Encoding ASCII $cmdFile

$bstr = [IntPtr]::Zero
try {
  $cred = Import-Clixml $CredentialFile
  $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($cred.Password)
  $pass = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)

  $args = @(
    "-unat=y",
    "-host=$HostName",
    "-port=$Port",
    "-user=$User",
    "-keypairFile=$KeyFile",
    "-keypairPass=$pass",
    "-elevation=y",
    "-exitZero",
    "-cmdFile=$cmdFile"
  )

  & $BitviseSexec @args
  if ($LASTEXITCODE -ne 0) {
    throw "sexec exited with code $LASTEXITCODE"
  }
}
finally {
  if ($bstr -ne [IntPtr]::Zero) {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
  }
  Remove-Item $cmdFile -ErrorAction SilentlyContinue
}
