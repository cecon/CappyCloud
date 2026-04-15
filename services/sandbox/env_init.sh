#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# CappyCloud Persistent Environment Init
#
# Runs once when a user's environment container starts.
# Clones the base repo into /workspace/main and starts ONE
# openclaude gRPC server that handles ALL sessions in this
# container (each ChatRequest specifies its own working_directory
# pointing to a git worktree under /workspace/sessions/).
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
WORKSPACE_REPO="${WORKSPACE_REPO:-}"
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

echo "Provider: OpenRouter  model=${OPENAI_MODEL}"

# ── Configure git authentication ─────────────────────────────
if [ -n "${GIT_AUTH_TOKEN}" ]; then
    # Azure DevOps — a non-empty username ('pat') is required for Basic auth to work
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
mkdir -p /workspace/main /workspace/sessions

# ── Clone or update base repo into /workspace/main ───────────
if [ -n "${WORKSPACE_REPO}" ]; then
    CLEAN_REPO=$(echo "${WORKSPACE_REPO}" | sed 's|https://[^@]*@|https://|')

    if [ -d /workspace/main/.git ]; then
        echo "Base repo already present — pulling latest..."
        cd /workspace/main && git pull --ff-only 2>&1 \
            || echo "WARNING: git pull failed — continuing with existing code."
    else
        echo "Cloning ${CLEAN_REPO} into /workspace/main..."
        if git clone --depth=1 "${CLEAN_REPO}" /workspace/main 2>&1; then
            echo "Clone successful."
        else
            echo "WARNING: git clone failed — initialising empty workspace."
            cd /workspace/main
            git init
            git config user.email "agent@cappycloud.local"
            git config user.name "CappyCloud Agent"
            git commit --allow-empty -m "init"
        fi
    fi
else
    echo "No WORKSPACE_REPO set — initialising empty git workspace."
    if [ ! -d /workspace/main/.git ]; then
        cd /workspace/main
        git init
        git config user.email "agent@cappycloud.local"
        git config user.name "CappyCloud Agent"
        git commit --allow-empty -m "init"
    fi
fi

# ── Inject agent instructions ─────────────────────────────────
# Place CLAUDE.md in /workspace/main so every worktree inherits it.
# Does NOT modify the git index — stays untracked inside the container.
if [ -f /app/CLAUDE.md ]; then
    cp /app/CLAUDE.md /workspace/main/CLAUDE.md
    echo "CLAUDE.md injected into /workspace/main."
fi

# ── Export provider env vars for openclaude ──────────────────
export CLAUDE_CODE_USE_OPENAI="${CLAUDE_CODE_USE_OPENAI}"
export OPENAI_BASE_URL="${OPENAI_BASE_URL}"
export OPENAI_API_KEY="${OPENAI_API_KEY}"
export OPENAI_MODEL="${OPENAI_MODEL}"
export GRPC_HOST="${GRPC_HOST}"
export GRPC_PORT="${GRPC_PORT}"

# ── Start the single openclaude gRPC server ───────────────────
# One process handles all concurrent sessions in this container.
# Each ChatRequest carries its own working_directory → correct worktree.
echo "Starting openclaude gRPC server on ${GRPC_HOST}:${GRPC_PORT}..."
cd /openclaude
exec npm run dev:grpc
