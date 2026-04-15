# ──────────────────────────────────────────────────────────────
# CappyCloud Sandbox Image
#
# Builds openclaude from source (supports gRPC headless mode via
# GRPC_HOST / GRPC_PORT env vars) and provides a git-enabled
# workspace environment.
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
    && rm -rf /var/lib/apt/lists/*

# ── Install Bun (required to build openclaude) ───────────────
RUN curl -fsSL https://bun.sh/install | bash
ENV PATH="/root/.bun/bin:${PATH}"

# ── Clone and build openclaude from source ────────────────────
# We clone at build time so the image is self-contained.
# Patch: Grep tool schema accepts `n` as alias for `-n` (some models emit `n`).
COPY patches/grep-tool-n-alias.patch /tmp/grep-tool-n-alias.patch
WORKDIR /openclaude
RUN git clone --depth=1 https://github.com/Gitlawb/openclaude.git . \
    && git apply /tmp/grep-tool-n-alias.patch \
    && rm -f /tmp/grep-tool-n-alias.patch \
    && bun install \
    && bun run build

# ── System tools needed at runtime (separate layer to preserve cache) ─
# ripgrep is required by openclaude for file search (Glob tool)
RUN apt-get update && apt-get install -y --no-install-recommends ripgrep \
    && rm -rf /var/lib/apt/lists/*

# ── Workspace directory (populated at runtime via git clone) ──
RUN mkdir -p /workspace
WORKDIR /workspace

# ── Agent instructions injected into every workspace ──────────
# CLAUDE.md is placed at /workspace root after git clone so openclaude
# picks it up automatically as its context file.
COPY CLAUDE.md /app/CLAUDE.md

# ── Entrypoint ────────────────────────────────────────────────
COPY entrypoint.sh /entrypoint.sh
# Fix Windows CRLF line endings → LF so bash can execute the script on Linux
RUN sed -i 's/\r//' /entrypoint.sh && chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
