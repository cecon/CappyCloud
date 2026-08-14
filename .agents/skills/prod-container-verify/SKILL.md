---
name: prod-container-verify
description: Verify CappyCloud production containers through the configured Bitvise SSH path. Use when asked to confirm prod, sandbox-prod, Portainer redeploys, Docker Swarm services, container health, image digests, or the OpenClaude version running inside the production sandbox container.
---

# Prod Container Verify

## Quick Start

Run the bundled script from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .agents/skills/prod-container-verify/scripts/verify-prod-container.ps1
```

The script connects to production with Bitvise `sexec`, reads the SSH key
passphrase from `~/.ssh/cappy-prod.password.clixml`, lists CappyCloud Swarm
services and containers, inspects the sandbox container, and runs:

```bash
node /openclaude/dist/cli.mjs --version
curl -fsS http://127.0.0.1:8080/runtime/status
```

## Required Local State

- Bitvise SSH Client installed at `C:\Program Files (x86)\Bitvise SSH Client\sexec.exe`.
- Production host: `191.235.116.32`, port `2499`, user `mpc-ai-user`.
- Client key: `F:\OneDriver\OneDrive\C3CON\Servers\LinxN8N.ppk`.
- Key passphrase stored as DPAPI for the current Windows user at
  `C:\Users\cecon\.ssh\cappy-prod.password.clixml`.

Never hardcode or print the passphrase. If the DPAPI file is missing, recreate
it from the user-provided passphrase with:

```powershell
$secure = Read-Host "Key passphrase" -AsSecureString
[pscredential]::new("mpc-ai-user", $secure) |
  Export-Clixml $HOME\.ssh\cappy-prod.password.clixml
```

## Expected Evidence

A successful verification should report:

- host `MPC-AI-DCK01`;
- `cappycloud_sandbox` service at `1/1`;
- sandbox container status `healthy`;
- sandbox image `ghcr.io/cecon/cappycloud-sandbox:latest@sha256:...`;
- `0.28.0 (OpenClaude)` or the version being validated;
- runtime status JSON with `openclaude` equal to `running`.

## Failure Notes

- OpenSSH may fail with `Permission denied (publickey)` even when Bitvise works;
  use `sexec` for this environment.
- Docker requires `sudo -n`; direct `docker ps` as `mpc-ai-user` returns socket
  permission denied.
- `sexec -cmdFile` executes each line independently. Keep remote commands as
  self-contained one-liners instead of relying on shell variables across lines.
