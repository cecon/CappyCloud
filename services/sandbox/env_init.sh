#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# CappyCloud Sandbox — Persistent Environment Init
#
# Roda quando o container sandbox sobe. O diretório /repos é um
# volume Docker persistente: repos sobrevivem a restarts/rebuilds.
#
# O que faz:
#   1. Configura git auth para Azure DevOps (DEVOPS_TOKEN) e/ou
#      GitHub (GITHUB_TOKEN) — cada um só se a variável estiver definida.
#   2. Clona repos listados em WORKSPACE_REPOS se ainda não existirem
#      no volume; se já existirem, faz git fetch para atualizar.
#   3. Aplica patch no context-window do openclaude para modelos OpenRouter.
#   4. Sobe session_server.js (HTTP :8080) em background.
#   5. Executa o servidor gRPC do openclaude (processo principal).
# ──────────────────────────────────────────────────────────────
set -euo pipefail

: "${OPENAI_API_KEY:?OPENAI_API_KEY is required}"

OPENAI_BASE_URL="${OPENAI_BASE_URL:-https://openrouter.ai/api/v1}"
OPENAI_MODEL="${OPENAI_MODEL:-anthropic/claude-3.5-sonnet}"
CLAUDE_CODE_USE_OPENAI="${CLAUDE_CODE_USE_OPENAI:-1}"
GRPC_HOST="${GRPC_HOST:-0.0.0.0}"
GRPC_PORT="${GRPC_PORT:-50051}"
SESSION_SERVER_PORT="${SESSION_SERVER_PORT:-8080}"
OPENCLAUDE_AUTO_APPROVE="${OPENCLAUDE_AUTO_APPROVE:-1}"
WORKSPACE_REPOS="${WORKSPACE_REPOS:-}"
WORKSPACE_BRANCH="${WORKSPACE_BRANCH:-main}"
DEVOPS_TOKEN="${DEVOPS_TOKEN:-}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"

# ── Configure openclaude ──────────────────────────────────────
mkdir -p ~/.claude
cat > ~/.claude/settings.json <<EOF
{
  "apiKeyHelper": null,
  "autoUpdaterStatus": "disabled"
}
EOF

echo "Provider: OpenRouter  model=${OPENAI_MODEL}"

# ── Git global identity ───────────────────────────────────────
git config --global user.email "${GIT_USER_EMAIL:-agent@cappycloud.local}"
git config --global user.name "${GIT_USER_NAME:-CappyCloud Agent}"

# ── Git authentication (por provedor) ────────────────────────
if [ -n "${DEVOPS_TOKEN}" ]; then
    git config --global url."https://pat:${DEVOPS_TOKEN}@dev.azure.com".insteadOf \
        "https://dev.azure.com"
    echo "Git auth: Azure DevOps configurado."
fi

if [ -n "${GITHUB_TOKEN}" ]; then
    git config --global url."https://x-token:${GITHUB_TOKEN}@github.com".insteadOf \
        "https://github.com"
    echo "Git auth: GitHub configurado."

    # Configura gh CLI para uso pelo agente
    echo "${GITHUB_TOKEN}" | gh auth login --with-token 2>/dev/null || true
fi

if [ -n "${DEVOPS_TOKEN}" ]; then
    # Configura az CLI para uso pelo agente
    az devops configure --defaults organization="" 2>/dev/null || true
    export AZURE_DEVOPS_EXT_PAT="${DEVOPS_TOKEN}"
fi

# ── Função: clonar ou atualizar um repo ──────────────────────
clone_or_update_repo() {
    local repo_url="$1"
    local slug
    slug=$(basename "${repo_url}" | sed 's/\.git$//')
    local repo_dir="/repos/${slug}"

    echo ""
    echo "==> Repo: ${slug}  (${repo_url})"
    mkdir -p "${repo_dir}"

    # Monta URL autenticada
    local auth_url="${repo_url}"
    if [ -n "${DEVOPS_TOKEN}" ]; then
        auth_url=$(echo "${auth_url}" | \
            sed "s|https://dev.azure.com|https://pat:${DEVOPS_TOKEN}@dev.azure.com|")
    fi
    if [ -n "${GITHUB_TOKEN}" ]; then
        auth_url=$(echo "${auth_url}" | \
            sed "s|https://github.com|https://x-token:${GITHUB_TOKEN}@github.com|")
    fi

    if [ -d "${repo_dir}/.git" ]; then
        # Volume já tem o repo — só atualiza
        echo "    Volume existente — atualizando (git fetch)..."
        local default_branch
        default_branch=$(git -C "${repo_dir}" remote show origin 2>/dev/null \
            | sed -n 's/.*HEAD branch: //p' | tr -d '[:space:]') || true
        default_branch="${default_branch:-${WORKSPACE_BRANCH}}"
        git -C "${repo_dir}" fetch origin "${default_branch}" 2>&1 \
            && git -C "${repo_dir}" checkout "${default_branch}" 2>/dev/null \
            && git -C "${repo_dir}" merge --ff-only "origin/${default_branch}" 2>&1 \
            || echo "    WARNING: git update falhou — continuando com código existente."
    else
        # Volume vazio ou repo ausente — clona
        local clone_ok=0
        for attempt in 1 2 3; do
            echo "    [clone attempt ${attempt}/3]"
            if git clone --depth=1 --branch "${WORKSPACE_BRANCH}" "${auth_url}" "${repo_dir}" 2>&1 || \
               git clone --depth=1 "${auth_url}" "${repo_dir}" 2>&1; then
                clone_ok=1; break
            fi
            [ "${attempt}" -lt 3 ] && echo "    Retrying in 3s..." && sleep 3
        done
        if [ "${clone_ok}" -eq 1 ]; then
            echo "    Clone OK."
        else
            echo "    WARNING: clone falhou — inicializando workspace vazio."
            git -C "${repo_dir}" init -b main 2>/dev/null || git -C "${repo_dir}" init
            git -C "${repo_dir}" commit --allow-empty -m "init" 2>/dev/null || true
        fi
    fi

    # Garante pelo menos um commit para worktrees funcionarem
    if ! git -C "${repo_dir}" rev-parse HEAD >/dev/null 2>&1; then
        git -C "${repo_dir}" commit --allow-empty -m "init"
    fi

    # Não copiamos CLAUDE.md para o clone principal — o repo pode ter o seu
    # próprio. A injeção só acontece nos worktrees de sessão (session_start.sh)
    # e mesmo aí só quando o repo não tem CLAUDE.md/AGENTS.md.

    mkdir -p "${repo_dir}/sessions"
}

# Repos são clonados via watchdog (DB → /repos/clone). Sandbox inicia sem pre-clone.
echo "Sandbox ready — repos will be cloned via watchdog (sandbox_sync_queue)."

# ── Patch openclaude: context-window para modelos OpenRouter ─
_TS=/openclaude/src/utils/model/openaiContextWindows.ts
if [ -f "$_TS" ]; then
    node - "$_TS" << 'PATCH_EOF'
const fs = require('fs');
const file = process.argv[2];
let c = fs.readFileSync(file, 'utf8');
const needle = "  // Groq (fast inference)\n  'llama-3.3-70b-versatile'";
const insert = [
  "  // OpenRouter-namespaced models",
  "  'openai/gpt-4o':                128_000,",
  "  'openai/gpt-4o-mini':           128_000,",
  "  'openai/gpt-4.1':             1_047_576,",
  "  'openai/gpt-4.1-mini':        1_047_576,",
  "  'openai/gpt-oss-120b':          128_000,",
  "  'openai/gpt-oss-120b:free':     128_000,",
  "  'openai/o1':                    200_000,",
  "  'openai/o3-mini':               200_000,",
  "  'anthropic/claude-3-haiku':     200_000,",
  "  'anthropic/claude-3-sonnet':    200_000,",
  "  'anthropic/claude-3.5-sonnet':  200_000,",
  "  'anthropic/claude-3-opus':      200_000,",
  "  'deepseek/deepseek-v3':         65_536,",
  "  'deepseek/deepseek-v3-0324':    65_536,",
  "  'deepseek/deepseek-v3.2':       65_536,",
  "  'deepseek/deepseek-chat':       65_536,",
  "  'deepseek/deepseek-r1':         65_536,",
  "",
].join('\n');
if (c.includes('openai/gpt-4o-mini')) {
  console.log('[env_init] context window patch: already present.');
  process.exit(0);
}
if (!c.includes(needle)) {
  console.log('[env_init] context window patch: needle not found, skipping.');
  process.exit(0);
}
fs.writeFileSync(file, c.replace(needle, insert + needle));
console.log('[env_init] openclaude context window patch applied.');
PATCH_EOF
fi

# ── Exporta vars para openclaude e session_server ────────────
export CLAUDE_CODE_USE_OPENAI="${CLAUDE_CODE_USE_OPENAI}"
export OPENAI_BASE_URL="${OPENAI_BASE_URL}"
export OPENAI_API_KEY="${OPENAI_API_KEY}"
export OPENAI_MODEL="${OPENAI_MODEL}"
export GRPC_HOST="${GRPC_HOST}"
export GRPC_PORT="${GRPC_PORT}"
export OPENCLAUDE_AUTO_APPROVE="${OPENCLAUDE_AUTO_APPROVE}"
export DEVOPS_TOKEN="${DEVOPS_TOKEN:-}"
export GITHUB_TOKEN="${GITHUB_TOKEN:-}"

# ── Sobe o session server em background ──────────────────────
echo ""
echo "Starting session server on :${SESSION_SERVER_PORT}..."
SESSION_SERVER_PORT="${SESSION_SERVER_PORT}" node /session_server.js &
SESSION_SERVER_PID=$!
echo "Session server PID: ${SESSION_SERVER_PID}"

# ── Inicia o servidor gRPC do openclaude (processo principal) ─
echo "Starting openclaude gRPC server on ${GRPC_HOST}:${GRPC_PORT}..."
cd /openclaude
exec npm run dev:grpc
