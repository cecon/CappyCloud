# ──────────────────────────────────────────────────────────────
# CappyCloud Sandbox Image
#
# Builds openclaude from source (supports gRPC headless mode via
# GRPC_HOST / GRPC_PORT env vars) and provides a git-enabled
# workspace environment.
#
# Architecture:
#   One container per user (persistent environment).
#   One openclaude gRPC server handles all sessions in the container.
#   Each conversation gets its own git worktree created via docker exec.
#
# Build once:
#   docker build -t cappycloud-sandbox:latest ./services/sandbox
# ──────────────────────────────────────────────────────────────
FROM node:20-slim

# ── System dependencies ───────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        curl \
        ca-certificates \
        unzip \
        ripgrep \
        jq \
    && rm -rf /var/lib/apt/lists/*

# ── Install Bun (required to build openclaude) ───────────────
RUN curl -fsSL https://bun.sh/install | bash
ENV PATH="/root/.bun/bin:${PATH}"

# ── Clone and build openclaude from source ────────────────────
# We clone at build time so the image is self-contained.
# Patches:
#   - grep-tool-n-alias.patch: Grep tool schema accepts `n` as alias for `-n`.
#   - auto-approve-tools.patch: gRPC server auto-allows tool calls when
#     OPENCLAUDE_AUTO_APPROVE=1 (skips action_required prompts).
COPY patches/grep-tool-n-alias.patch /tmp/grep-tool-n-alias.patch
COPY patches/auto-approve-tools.patch /tmp/auto-approve-tools.patch
WORKDIR /openclaude
RUN git clone --depth=1 https://github.com/Gitlawb/openclaude.git . \
    && git apply /tmp/grep-tool-n-alias.patch \
    && git apply /tmp/auto-approve-tools.patch \
    && rm -f /tmp/grep-tool-n-alias.patch /tmp/auto-approve-tools.patch \
    && bun install \
    && bun run build

# ── System tools needed at runtime (separate layer to preserve cache) ─
# ripgrep is required by openclaude for file search (Glob tool)
RUN apt-get update && apt-get install -y --no-install-recommends ripgrep \
    && rm -rf /var/lib/apt/lists/*

# ── Workspace directory (populated at runtime via git clone) ──
# /repos/<slug>/ → clone do repo; criado pelo env_init.sh no start
RUN mkdir -p /repos
WORKDIR /repos

# ── Agent instructions injected into every workspace ──────────
# CLAUDE.md is placed in each worktree by session_start.sh so openclaude
# picks it up automatically as its context file.
COPY CLAUDE.md /app/CLAUDE.md

# ── Entrypoints ───────────────────────────────────────────────
# env_init.sh  — runs once when the persistent container starts:
#                clones the base repo + starts the single gRPC server
# session_start.sh — called via `docker exec` for each new conversation:
#                    creates a git worktree at /workspace/sessions/<id>
COPY env_init.sh /env_init.sh
COPY session_start.sh /session_start.sh
# Fix Windows CRLF line endings → LF so bash can execute scripts on Linux
RUN sed -i 's/\r//' /env_init.sh /session_start.sh \
    && chmod +x /env_init.sh /session_start.sh

# ── cappy-search CLI (wraps o Code Indexer HTTP API) ──────────
COPY cappy-search /usr/local/bin/cappy-search
RUN sed -i 's/\r//' /usr/local/bin/cappy-search \
    && chmod +x /usr/local/bin/cappy-search

ENTRYPOINT ["/env_init.sh"]
