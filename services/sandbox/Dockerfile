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
        python3 \
        python3-pip \
        python3-venv \
        graphviz \
        fonts-dejavu-core \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# ── Python libs para geração de artefactos (relatórios, diagramas) ──
# Instalados system-wide (--break-system-packages é seguro neste container
# isolado e elimina a fricção de venv para cada task do agente).
RUN pip3 install --no-cache-dir --break-system-packages \
        python-docx==1.1.2 \
        openpyxl==3.1.5 \
        matplotlib==3.9.2 \
        pillow==10.4.0 \
        graphviz==0.20.3 \
        networkx==3.3 \
        reportlab==4.2.5 \
        markdown==3.7 \
        weasyprint==62.3 \
        pyyaml==6.0.2 \
        jinja2==3.1.4 \
        requests==2.32.3 \
        ruff==0.15.13 \
        libcst==1.8.6 \
        basedpyright==1.39.4

# ── Semantic code tooling (on-demand LSP/AST helpers) ─────────
# Estes binários ficam disponíveis para o agente e para MCPs configurados pelo
# utilizador, mas nenhum language server fica residente por padrão.
RUN npm install -g \
        typescript@6.0.3 \
        typescript-language-server@5.2.0 \
        pyright@1.1.409 \
        @ast-grep/cli@0.42.2 \
        tree-sitter-cli@0.22.6 \
        ts-morph@28.0.0 \
    && npm cache clean --force
ENV NODE_PATH="/usr/local/lib/node_modules"

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
ARG OPENCLAUDE_REF=f71e7692373a61d28c82fc3fadff3feaa4071ede
COPY patches/grep-tool-n-alias.patch /tmp/grep-tool-n-alias.patch
COPY patches/auto-approve-tools.patch /tmp/auto-approve-tools.patch
COPY patches/multimodal-proto.patch /tmp/multimodal-proto.patch
COPY patches/multimodal-grpc-handler.patch /tmp/multimodal-grpc-handler.patch
COPY patches/mcp-grpc-integration.patch /tmp/mcp-grpc-integration.patch
COPY patches/worktree-tool-guard.patch /tmp/worktree-tool-guard.patch
COPY patches/numeric-parameter-grep-guard.patch /tmp/numeric-parameter-grep-guard.patch
COPY patches/numeric-parameter-grep-wrapper.patch /tmp/numeric-parameter-grep-wrapper.patch
RUN sed -i 's/\r$//' /tmp/*.patch
WORKDIR /openclaude
RUN git init . \
    && git remote add origin https://github.com/Gitlawb/openclaude.git \
    && git fetch --depth=1 origin "${OPENCLAUDE_REF}" \
    && git checkout FETCH_HEAD \
    && git apply /tmp/grep-tool-n-alias.patch \
    && git apply /tmp/auto-approve-tools.patch \
    && git apply /tmp/multimodal-proto.patch \
    && git apply /tmp/multimodal-grpc-handler.patch \
    && git apply /tmp/mcp-grpc-integration.patch \
    && git apply /tmp/worktree-tool-guard.patch \
    && git apply /tmp/numeric-parameter-grep-guard.patch \
    && git apply /tmp/numeric-parameter-grep-wrapper.patch \
    && sed -i 's/^detectStubLeaks()$/setImmediate(() => detectStubLeaks())/' src/entrypoints/sdk/index.ts \
    && rm -f /tmp/grep-tool-n-alias.patch /tmp/auto-approve-tools.patch \
            /tmp/multimodal-proto.patch /tmp/multimodal-grpc-handler.patch \
            /tmp/mcp-grpc-integration.patch /tmp/worktree-tool-guard.patch \
            /tmp/numeric-parameter-grep-guard.patch \
            /tmp/numeric-parameter-grep-wrapper.patch \
    && bun install \
    && bun run build

# ── signoz-mcp-server (binário Go, modo stdio) ────────────────
# Detecta a arquitetura em runtime para suportar amd64 e arm64.
# Extrai para /tmp e move o binário para evitar problemas com paths internos
# do tarball. command = /usr/local/bin/signoz-mcp-server
RUN ARCH=$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/') \
    && mkdir /tmp/signoz-extract \
    && curl -fsSL \
       "https://github.com/SigNoz/signoz-mcp-server/releases/latest/download/signoz-mcp-server_linux_${ARCH}.tar.gz" \
       | tar xz -C /tmp/signoz-extract \
    && find /tmp/signoz-extract -maxdepth 3 \( -name 'signoz-mcp-server' -o -name 'server' \) -type f \
       | head -1 | xargs -I{} install -m 755 {} /usr/local/bin/signoz-mcp-server \
    && rm -rf /tmp/signoz-extract

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
COPY git_handlers.js /git_handlers.js
COPY mcp_handler.js /mcp_handler.js
COPY confluence_handler.js /confluence_handler.js
COPY repo_handlers.js /repo_handlers.js
COPY repo_graph /repo_graph
COPY repo_graph_handlers.js /repo_graph_handlers.js
COPY task_handler.js /task_handler.js
COPY worktree_handlers.js /worktree_handlers.js
COPY confluence_mcp_lib.py /usr/local/bin/confluence_mcp_lib.py
COPY confluence_mcp_server.py /usr/local/bin/confluence-mcp-server
RUN sed -i 's/\r//' /env_init.sh /session_start.sh \
    && chmod +x /env_init.sh /session_start.sh /usr/local/bin/confluence-mcp-server

ENTRYPOINT ["/env_init.sh"]
