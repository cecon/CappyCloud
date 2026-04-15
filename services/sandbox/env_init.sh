#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# CappyCloud Persistent Environment Init
#
# Runs once when a global environment container starts.
# Clones the base repo into /repos/<ENV_SLUG>/ and starts ONE
# openclaude gRPC server that handles ALL sessions in this
# container (each ChatRequest specifies its own working_directory
# pointing to a git worktree under /repos/<slug>/sessions/).
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

MAIN_REPO="/repos/${ENV_SLUG}"

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

# Default git identity for worktree commits
git config --global user.email "${GIT_USER_EMAIL:-agent@cappycloud.local}"
git config --global user.name "${GIT_USER_NAME:-CappyCloud Agent}"

# ── Create workspace structure ────────────────────────────────
mkdir -p "${MAIN_REPO}"

# ── Clone or update base repo into /repos/<slug>/ ────────────
if [ -n "${WORKSPACE_REPO}" ]; then
    CLEAN_REPO=$(echo "${WORKSPACE_REPO}" | sed 's|https://[^@]*@|https://|')

    # Monta URL autenticada diretamente para evitar dependência de insteadOf no clone inicial
    if [ -n "${GIT_AUTH_TOKEN}" ]; then
        AUTH_REPO=$(echo "${CLEAN_REPO}" | sed "s|https://dev.azure.com|https://pat:${GIT_AUTH_TOKEN}@dev.azure.com|" | \
            sed "s|https://github.com|https://x-token:${GIT_AUTH_TOKEN}@github.com|")
    else
        AUTH_REPO="${CLEAN_REPO}"
    fi

    if [ -d "${MAIN_REPO}/.git" ]; then
        echo "Base repo already present — pulling latest..."
        cd "${MAIN_REPO}" && git pull --ff-only 2>&1 \
            || echo "WARNING: git pull failed — continuing with existing code."
    else
        echo "Cloning ${CLEAN_REPO} (branch=${WORKSPACE_BRANCH}) into ${MAIN_REPO}..."
        CLONE_OK=0
        for attempt in 1 2 3; do
            echo "[clone attempt ${attempt}/3]"
            if git clone --depth=1 --branch "${WORKSPACE_BRANCH}" "${AUTH_REPO}" "${MAIN_REPO}" 2>&1; then
                CLONE_OK=1; break
            fi
            if git clone --depth=1 "${AUTH_REPO}" "${MAIN_REPO}" 2>&1; then
                CLONE_OK=1; break
            fi
            [ "${attempt}" -lt 3 ] && echo "Retrying in 3s..." && sleep 3
        done
        if [ "${CLONE_OK}" -eq 1 ]; then
            echo "Clone successful."
        else
            echo "WARNING: git clone failed after 3 attempts — initialising empty workspace."
        fi
    fi
else
    echo "No WORKSPACE_REPO set — initialising empty git workspace at ${MAIN_REPO}."
fi

# Garante repo git com commit válido para os worktrees funcionarem.
if [ ! -d "${MAIN_REPO}/.git" ]; then
    cd "${MAIN_REPO}" && git init
fi
if ! git -C "${MAIN_REPO}" rev-parse HEAD >/dev/null 2>&1; then
    git -C "${MAIN_REPO}" commit --allow-empty -m "init"
fi

# ── Inject agent instructions ─────────────────────────────────
if [ -f /app/CLAUDE.md ]; then
    cp /app/CLAUDE.md "${MAIN_REPO}/CLAUDE.md"
    echo "CLAUDE.md injected into ${MAIN_REPO}."
fi

# ── Garante pasta de worktrees ────────────────────────────────
mkdir -p "/repos/${ENV_SLUG}/sessions"

# ── Export provider env vars for openclaude ──────────────────
export CLAUDE_CODE_USE_OPENAI="${CLAUDE_CODE_USE_OPENAI}"
export OPENAI_BASE_URL="${OPENAI_BASE_URL}"
export OPENAI_API_KEY="${OPENAI_API_KEY}"
export OPENAI_MODEL="${OPENAI_MODEL}"
export GRPC_HOST="${GRPC_HOST}"
export GRPC_PORT="${GRPC_PORT}"

# ── Start the single openclaude gRPC server ───────────────────
echo "Starting openclaude gRPC server on ${GRPC_HOST}:${GRPC_PORT}..."
cd /openclaude
exec npm run dev:grpc
