# ──────────────────────────────────────────────────────────────
# CappyCloud Sandbox Image
#
# Sandbox permanente configurado como VM de desenvolvimento:
#   - git, GitHub CLI (gh), Azure CLI (az) + azure-devops extension
#   - openclaude gRPC headless server
#   - session_server.js: HTTP server que gerencia worktrees por sessão
#
# /repos é montado como volume Docker (dados persistem entre restarts).
# Cada conversa ganha um git worktree em /repos/<slug>/sessions/<id>/
# criado via HTTP POST /sessions no session_server.
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
        gnupg \
        lsb-release \
    && rm -rf /var/lib/apt/lists/*

# ── GitHub CLI (gh) ───────────────────────────────────────────
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

# ── Azure CLI + azure-devops extension ───────────────────────
# Usa o script oficial da Microsoft para garantir versão recente compatível
# com a extensão azure-devops (o pacote Debian nativo é antigo demais).
RUN curl -sL https://aka.ms/InstallAzureCLIDeb | bash \
    && az extension add --name azure-devops \
    && rm -rf /var/lib/apt/lists/*

# ── Install Bun (required to build openclaude) ───────────────
RUN curl -fsSL https://bun.sh/install | bash
ENV PATH="/root/.bun/bin:${PATH}"

# ── Clone and build openclaude from source ────────────────────
COPY patches/grep-tool-n-alias.patch /tmp/grep-tool-n-alias.patch
COPY patches/auto-approve-tools.patch /tmp/auto-approve-tools.patch
WORKDIR /openclaude
RUN git clone --depth=1 https://github.com/Gitlawb/openclaude.git . \
    && git apply /tmp/grep-tool-n-alias.patch \
    && git apply /tmp/auto-approve-tools.patch \
    && rm -f /tmp/grep-tool-n-alias.patch /tmp/auto-approve-tools.patch \
    && bun install \
    && bun run build

# ── /repos layout (volume montado em runtime) ─────────────────
# O volume repos_data é montado aqui. RUN mkdir garante que o
# diretório existe na imagem para o caso de inicialização sem volume.
RUN mkdir -p /repos
WORKDIR /repos

# ── Agent instructions injected into every workspace ──────────
COPY CLAUDE.md /app/CLAUDE.md

# ── Entrypoints e scripts ─────────────────────────────────────
COPY env_init.sh /env_init.sh
COPY session_start.sh /session_start.sh
COPY session_server.js /session_server.js
RUN sed -i 's/\r//' /env_init.sh /session_start.sh \
    && chmod +x /env_init.sh /session_start.sh

ENTRYPOINT ["/env_init.sh"]
