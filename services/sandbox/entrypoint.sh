#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# CappyCloud Sandbox Entrypoint
#
# 1. Writes openclaude settings for OpenRouter (or any OpenAI-
#    compatible provider set via env vars).
# 2. Clones the git workspace into /repos/<ENV_SLUG>/
# 3. Starts openclaude in gRPC headless server mode.
# ──────────────────────────────────────────────────────────────
set -euo pipefail

# ── Required env vars ─────────────────────────────────────────
: "${OPENAI_API_KEY:?OPENAI_API_KEY is required}"

# ── Defaults ──────────────────────────────────────────────────
OPENAI_BASE_URL="${OPENAI_BASE_URL:-https://openrouter.ai/api/v1}"
OPENAI_MODEL="${OPENAI_MODEL:-anthropic/claude-3.5-sonnet}"
CLAUDE_CODE_USE_OPENAI="${CLAUDE_CODE_USE_OPENAI:-1}"
GRPC_HOST="${GRPC_HOST:-0.0.0.0}"
GRPC_PORT="${GRPC_PORT:-50051}"
ENV_SLUG="${ENV_SLUG:-default}"
WORKSPACE_REPO="${WORKSPACE_REPO:-}"
WORKSPACE_BRANCH="${WORKSPACE_BRANCH:-main}"
GIT_AUTH_TOKEN="${GIT_AUTH_TOKEN:-}"
AZURE_ORG="${AZURE_ORG:-}"

# ── Configure openclaude ──────────────────────────────────────
mkdir -p ~/.claude

cat > ~/.claude/settings.json <<EOF
{
  "apiKeyHelper": null,
  "autoUpdaterStatus": "disabled"
}
EOF

echo "Provider: OpenRouter  model=${OPENAI_MODEL}  env=${ENV_SLUG}"

# ── Configure git authentication ─────────────────────────────
if [ -n "${GIT_AUTH_TOKEN}" ]; then
    git config --global url."https://pat:${GIT_AUTH_TOKEN}@dev.azure.com".insteadOf \
        "https://dev.azure.com"

    if [ -n "${AZURE_ORG:-}" ]; then
        git config --global url."https://pat:${GIT_AUTH_TOKEN}@dev.azure.com/${AZURE_ORG}".insteadOf \
            "https://${AZURE_ORG}@dev.azure.com/${AZURE_ORG}"
    fi

    git config --global url."https://x-token:${GIT_AUTH_TOKEN}@github.com".insteadOf \
        "https://github.com"

    echo "Git credentials configured via insteadOf."
fi

# ── Prepare workspace layout ─────────────────────────────────
# /repos/<slug>/          → clone principal do repo
# /repos/<slug>/sessions/ → worktrees por conversa (session_start.sh)
MAIN_REPO="/repos/${ENV_SLUG}"
mkdir -p "${MAIN_REPO}" "/repos/${ENV_SLUG}/sessions"

if [ -n "${WORKSPACE_REPO}" ]; then
    CLEAN_REPO=$(echo "${WORKSPACE_REPO}" | sed 's|https://[^@]*@|https://|')

    # Monta URL autenticada diretamente para evitar dependência de insteadOf no clone
    if [ -n "${GIT_AUTH_TOKEN}" ]; then
        AUTH_REPO=$(echo "${CLEAN_REPO}" | sed "s|https://dev.azure.com|https://pat:${GIT_AUTH_TOKEN}@dev.azure.com|")
    else
        AUTH_REPO="${CLEAN_REPO}"
    fi

    if [ -d "${MAIN_REPO}/.git" ]; then
        echo "Workspace already cloned — running git pull..."
        cd "${MAIN_REPO}" && git pull --ff-only 2>&1 || echo "WARNING: git pull failed — continuing."
    else
        echo "Cloning ${CLEAN_REPO} (branch=${WORKSPACE_BRANCH}) into ${MAIN_REPO}..."
        CLONE_OK=0
        for attempt in 1 2 3; do
            echo "[clone attempt ${attempt}/3]"
            if git clone --depth=1 --branch "${WORKSPACE_BRANCH}" "${AUTH_REPO}" "${MAIN_REPO}" 2>&1; then
                CLONE_OK=1
                break
            fi
            if git clone --depth=1 "${AUTH_REPO}" "${MAIN_REPO}" 2>&1; then
                CLONE_OK=1
                break
            fi
            [ "${attempt}" -lt 3 ] && sleep 3
        done
        if [ "${CLONE_OK}" -eq 1 ]; then
            echo "Clone successful."
        else
            echo "WARNING: git clone failed after 3 attempts — starting with empty workspace."
        fi
    fi
else
    echo "No WORKSPACE_REPO set — starting with empty workspace at ${MAIN_REPO}."
fi

# Garante que existe um repo git (com pelo menos um commit) para os worktrees funcionarem.
if [ ! -d "${MAIN_REPO}/.git" ]; then
    git -C "${MAIN_REPO}" init -b main
fi
if ! git -C "${MAIN_REPO}" rev-parse HEAD >/dev/null 2>&1; then
    git -C "${MAIN_REPO}" config user.email "agent@cappycloud.local"
    git -C "${MAIN_REPO}" config user.name "CappyCloud Agent"
    git -C "${MAIN_REPO}" commit --allow-empty -m "initial"
fi

# Sem injeção de CLAUDE.md no clone principal — preservamos o ficheiro
# original do repo. O CLAUDE.md genérico do CappyCloud é só copiado para o
# worktree de cada sessão, e apenas se o repo não tiver já um.

# ── Auto-registro no CappyCloud API ─────────────────────────
# O container se registra como sandbox ativo ao iniciar.
# Requer SANDBOX_REGISTER_TOKEN e API_HOST configurados.
SANDBOX_REGISTER_TOKEN="${SANDBOX_REGISTER_TOKEN:-}"
SANDBOX_NAME="${SANDBOX_NAME:-cappycloud-sandbox}"
API_HOST="${API_HOST:-cappycloud-api}"
API_PORT_INTERNAL="${API_PORT_INTERNAL:-8080}"

if [ -n "${SANDBOX_REGISTER_TOKEN}" ]; then
    # Tenta registrar via curl — falha não-fatal (não impede o sandbox de rodar).
    SANDBOX_HOST="${SANDBOX_HOST:-$(hostname -i 2>/dev/null || echo "${API_HOST}")}"
    for attempt in 1 2 3 4; do
        REGISTER_RESP=$(curl -sf -X POST \
            "http://${API_HOST}:${API_PORT_INTERNAL}/api/sandboxes/register" \
            -H "Content-Type: application/json" \
            -d "{\"name\":\"${SANDBOX_NAME}\",\"host\":\"${SANDBOX_HOST}\",\"grpc_port\":${GRPC_PORT},\"session_port\":${SESSION_SERVER_PORT:-8080},\"register_token\":\"${SANDBOX_REGISTER_TOKEN}\"}" \
            2>&1) && echo "Sandbox '${SANDBOX_NAME}' registrado (host=${SANDBOX_HOST})." && break
        WAIT=$((attempt * 2))
        echo "Registro falhou (tentativa ${attempt}/4) — aguardando ${WAIT}s..."
        sleep "${WAIT}"
    done
else
    echo "SANDBOX_REGISTER_TOKEN não configurado — pulando auto-registro."
fi

# ── Export provider env vars for openclaude ──────────────────
export CLAUDE_CODE_USE_OPENAI="${CLAUDE_CODE_USE_OPENAI}"
export OPENAI_BASE_URL="${OPENAI_BASE_URL}"
export OPENAI_API_KEY="${OPENAI_API_KEY}"
export OPENAI_MODEL="${OPENAI_MODEL}"
export GRPC_HOST="${GRPC_HOST}"
export GRPC_PORT="${GRPC_PORT}"

# ── Start openclaude gRPC headless server ─────────────────────
echo "Starting openclaude gRPC server on ${GRPC_HOST}:${GRPC_PORT}..."
cd /openclaude
exec npm run dev:grpc
