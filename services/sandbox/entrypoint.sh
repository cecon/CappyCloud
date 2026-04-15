#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# CappyCloud Sandbox Entrypoint
#
# 1. Writes openclaude settings for OpenRouter (or any OpenAI-
#    compatible provider set via env vars).
# 2. Optionally clones a git workspace.
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
# Uses the `insteadOf` technique: rewrites plain https:// URLs to include
# the PAT before they reach the server. This works regardless of whether
# the original URL contains an embedded username (user@host).
if [ -n "${GIT_AUTH_TOKEN}" ]; then
    # Azure DevOps — rewrite both the plain URL and the user-embedded form
    git config --global url."https://:${GIT_AUTH_TOKEN}@dev.azure.com".insteadOf \
        "https://dev.azure.com"

    # Handle URLs with embedded username: https://anyuser@dev.azure.com/...
    # Git normalises these to https://dev.azure.com/... before credential
    # lookup, so the rule above already covers them. But add an explicit
    # per-org rule just in case:
    if [ -n "${AZURE_ORG:-}" ]; then
        git config --global url."https://:${GIT_AUTH_TOKEN}@dev.azure.com/${AZURE_ORG}".insteadOf \
            "https://${AZURE_ORG}@dev.azure.com/${AZURE_ORG}"
    fi

    # GitHub PAT fallback
    git config --global url."https://x-token:${GIT_AUTH_TOKEN}@github.com".insteadOf \
        "https://github.com"

    echo "Git credentials configured via insteadOf."
fi

# ── Clone or update workspace ─────────────────────────────────
if [ -n "${WORKSPACE_REPO}" ]; then
    # Strip embedded username — auth is handled by the insteadOf git config above
    CLEAN_REPO=$(echo "${WORKSPACE_REPO}" | sed 's|https://[^@]*@|https://|')

    if [ -d /workspace/.git ]; then
        echo "Workspace already cloned — running git pull to get latest code..."
        cd /workspace && git pull --ff-only 2>&1 || echo "WARNING: git pull failed — continuing with existing code."
    else
        echo "Cloning ${CLEAN_REPO} into /workspace..."
        if git clone --depth=1 "${CLEAN_REPO}" /workspace 2>&1; then
            echo "Clone successful."
        else
            echo "WARNING: git clone failed — starting with empty workspace."
        fi
    fi
else
    echo "No WORKSPACE_REPO set — starting with empty workspace."
fi

# ── Inject agent instructions ─────────────────────────────────
# Copy CLAUDE.md into the workspace root so openclaude reads it
# automatically as context. This does NOT modify the git repo —
# it only exists inside this container's filesystem.
if [ -f /app/CLAUDE.md ]; then
    cp /app/CLAUDE.md /workspace/CLAUDE.md
    echo "CLAUDE.md injected into workspace."
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
