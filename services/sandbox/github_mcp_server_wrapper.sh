#!/usr/bin/env bash
set -euo pipefail

if [ -z "${GITHUB_PERSONAL_ACCESS_TOKEN:-}" ] && [ -n "${GITHUB_TOKEN:-}" ]; then
    export GITHUB_PERSONAL_ACCESS_TOKEN="${GITHUB_TOKEN}"
fi

if [ -z "${GITHUB_PERSONAL_ACCESS_TOKEN:-}" ] && command -v gh >/dev/null 2>&1; then
    GH_TOKEN_FROM_CLI="$(gh auth token 2>/dev/null || true)"
    if [ -n "${GH_TOKEN_FROM_CLI}" ]; then
        export GITHUB_PERSONAL_ACCESS_TOKEN="${GH_TOKEN_FROM_CLI}"
    fi
    unset GH_TOKEN_FROM_CLI
fi

if [ "${1:-}" = "stdio" ]; then
    exec /usr/local/bin/github-mcp-server "$@"
fi

exec /usr/local/bin/github-mcp-server stdio "$@"
