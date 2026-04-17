#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# CappyCloud Persistent Environment Init
#
# Runs once when the fixed sandbox container starts.
# Clones ALL repos listed in WORKSPACE_REPOS (comma-separated)
# into /repos/<slug>/ and starts ONE openclaude gRPC server.
#
# Each repo slug is derived from the last URL segment:
#   https://dev.azure.com/org/proj/_git/myrepo  →  myrepo
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
# Auto-aprova chamadas de ferramentas (skip do prompt action_required no gRPC).
# Set explicitly to "0" to require manual approval per tool call.
OPENCLAUDE_AUTO_APPROVE="${OPENCLAUDE_AUTO_APPROVE:-1}"
WORKSPACE_REPOS="${WORKSPACE_REPOS:-}"
WORKSPACE_BRANCH="${WORKSPACE_BRANCH:-main}"
GIT_AUTH_TOKEN="${GIT_AUTH_TOKEN:-}"

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
    git config --global url."https://pat:${GIT_AUTH_TOKEN}@dev.azure.com".insteadOf \
        "https://dev.azure.com"
    git config --global url."https://x-token:${GIT_AUTH_TOKEN}@github.com".insteadOf \
        "https://github.com"
    echo "Git credentials configured via insteadOf."
fi

git config --global user.email "${GIT_USER_EMAIL:-agent@cappycloud.local}"
git config --global user.name "${GIT_USER_NAME:-CappyCloud Agent}"

# ── Clone each repo from WORKSPACE_REPOS ─────────────────────
clone_repo() {
    local repo_url="$1"
    local slug
    slug=$(basename "${repo_url}" | sed 's/\.git$//')
    local repo_dir="/repos/${slug}"

    echo ""
    echo "==> Repo: ${slug}  (${repo_url})"
    mkdir -p "${repo_dir}"

    # Build authenticated URL
    local auth_url="${repo_url}"
    if [ -n "${GIT_AUTH_TOKEN}" ]; then
        auth_url=$(echo "${repo_url}" | \
            sed "s|https://dev.azure.com|https://pat:${GIT_AUTH_TOKEN}@dev.azure.com|" | \
            sed "s|https://github.com|https://x-token:${GIT_AUTH_TOKEN}@github.com|")
    fi

    if [ -d "${repo_dir}/.git" ]; then
        echo "    Already cloned — fetching latest..."
        # Always fetch the default branch by name to avoid "no tracking info" errors.
        # HEAD of the main clone must stay on the original branch (not a worktree branch).
        local default_branch
        default_branch=$(git -C "${repo_dir}" remote show origin 2>/dev/null \
            | sed -n 's/.*HEAD branch: //p' | tr -d '[:space:]') || true
        if [ -z "${default_branch}" ]; then
            default_branch="${WORKSPACE_BRANCH:-main}"
        fi
        git -C "${repo_dir}" fetch origin "${default_branch}" 2>&1 \
            && git -C "${repo_dir}" checkout "${default_branch}" 2>/dev/null \
            && git -C "${repo_dir}" merge --ff-only "origin/${default_branch}" 2>&1 \
            || echo "    WARNING: git update failed — continuing with existing code."
    else
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
            echo "    WARNING: clone failed — initialising empty workspace."
            git -C "${repo_dir}" init -b main 2>/dev/null || git -C "${repo_dir}" init
            git -C "${repo_dir}" commit --allow-empty -m "init" 2>/dev/null || true
        fi
    fi

    # Ensure at least one commit so worktrees work
    if ! git -C "${repo_dir}" rev-parse HEAD >/dev/null 2>&1; then
        git -C "${repo_dir}" commit --allow-empty -m "init"
    fi

    # Inject CLAUDE.md
    if [ -f /app/CLAUDE.md ]; then
        cp /app/CLAUDE.md "${repo_dir}/CLAUDE.md"
        echo "    CLAUDE.md injected."
    fi

    # Ensure sessions directory
    mkdir -p "${repo_dir}/sessions"
}

if [ -n "${WORKSPACE_REPOS}" ]; then
    IFS=',' read -ra REPO_LIST <<< "${WORKSPACE_REPOS}"
    for repo in "${REPO_LIST[@]}"; do
        repo=$(echo "${repo}" | tr -d '[:space:]')
        [ -n "${repo}" ] && clone_repo "${repo}"
    done
else
    echo "No WORKSPACE_REPOS set — sandbox starts without any repos."
fi

# ── Patch openclaude context-window table for OpenRouter models ──
# Adds models not shipped with openclaude so the "not in context window table"
# warning does not appear at runtime. Safe to run multiple times (idempotent).
_TS=/openclaude/src/utils/model/openaiContextWindows.ts
if [ -f "$_TS" ]; then
    node - "$_TS" << 'PATCH_EOF'
const fs = require('fs');
const file = process.argv[2];
let c = fs.readFileSync(file, 'utf8');
// OpenRouter prefixes models with "openai/", "anthropic/", etc.
// Add common OpenRouter-namespaced model names that map to known context windows.
const needle = "  // Groq (fast inference)\n  'llama-3.3-70b-versatile'";
const insert = [
  "  // OpenRouter-namespaced models (provider/model format used by OpenRouter API)",
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

# ── Export provider env vars for openclaude ──────────────────
export CLAUDE_CODE_USE_OPENAI="${CLAUDE_CODE_USE_OPENAI}"
export OPENAI_BASE_URL="${OPENAI_BASE_URL}"
export OPENAI_API_KEY="${OPENAI_API_KEY}"
export OPENAI_MODEL="${OPENAI_MODEL}"
export GRPC_HOST="${GRPC_HOST}"
export GRPC_PORT="${GRPC_PORT}"
export OPENCLAUDE_AUTO_APPROVE="${OPENCLAUDE_AUTO_APPROVE}"

# ── Start the single openclaude gRPC server ───────────────────
echo ""
echo "Starting openclaude gRPC server on ${GRPC_HOST}:${GRPC_PORT}..."
cd /openclaude
exec npm run dev:grpc
