# CappyCloud Sandbox Image
#
# Sandbox permanente configurado como VM de desenvolvimento:
#   - git, GitHub CLI (gh), Azure CLI (az) + azure-devops extension
#   - openclaude gRPC headless server
#   - session_server.js: HTTP server que gerencia worktrees por sessao
#
# /repos e montado como volume Docker (dados persistem entre restarts).

FROM golang:1.25-bookworm AS github-mcp-builder

ARG GITHUB_MCP_REF=v1.4.0
WORKDIR /src
RUN git clone --depth=1 --branch "${GITHUB_MCP_REF}" \
        https://github.com/github/github-mcp-server.git . \
    && CGO_ENABLED=0 go build -o /out/github-mcp-server ./cmd/github-mcp-server

FROM node:20-slim

# System dependencies
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

# Python libs para geracao de artefatos (relatorios, diagramas).
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

# Semantic code tooling (on-demand LSP/AST helpers).
RUN npm install -g \
        typescript@6.0.3 \
        typescript-language-server@5.2.0 \
        pyright@1.1.409 \
        @ast-grep/cli@0.42.2 \
        tree-sitter-cli@0.22.6 \
        ts-morph@28.0.0 \
    && npm cache clean --force
ENV NODE_PATH="/usr/local/lib/node_modules"

# GitHub CLI (gh)
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

# Azure CLI + azure-devops extension
RUN curl -sL https://aka.ms/InstallAzureCLIDeb | bash \
    && az extension add --name azure-devops \
    && rm -rf /var/lib/apt/lists/*

# Install Bun (required to build openclaude)
RUN curl -fsSL https://bun.sh/install | bash
ENV PATH="/root/.bun/bin:${PATH}"

# Clone and build openclaude from source
ARG OPENCLAUDE_REF=2ff93a10bf88ab6d7030fc4ade5316a7424fa2f9
COPY services/sandbox/patches/grep-tool-n-alias.patch /tmp/grep-tool-n-alias.patch
COPY services/sandbox/patches/multimodal-proto.patch /tmp/multimodal-proto.patch
COPY services/sandbox/patches/multimodal-grpc-handler.patch /tmp/multimodal-grpc-handler.patch
COPY services/sandbox/patches/read-empty-pages.patch /tmp/read-empty-pages.patch
COPY services/sandbox/patch_openclaude_grpc_v024.js /tmp/patch_openclaude_grpc_v024.js
COPY services/sandbox/cappycloud_grpc_helpers_v024.ts /tmp/cappycloud_grpc_helpers_v024.ts
COPY services/sandbox/cappycloud_grpc_diagnostics_v024.ts /tmp/cappycloud_grpc_diagnostics_v024.ts
RUN sed -i 's/\r$//' /tmp/*.patch
WORKDIR /openclaude
RUN git init . \
    && git remote add origin https://github.com/Gitlawb/openclaude.git \
    && git fetch --depth=1 origin "${OPENCLAUDE_REF}" \
    && git checkout FETCH_HEAD \
    && git apply /tmp/grep-tool-n-alias.patch \
    && git apply /tmp/multimodal-proto.patch \
    && git apply --reject /tmp/multimodal-grpc-handler.patch || true \
    && git apply /tmp/read-empty-pages.patch \
    && perl -0pi -e "s/if \\(toolUseID\\) \\{\\n                toolNameById\\.set\\(toolUseID, tool\\.name\\)\\n              \\}\\n              \\/\\/ Notify client of the tool call first/if (toolUseID) {\\n                toolNameById.set(toolUseID, tool.name)\\n              }\\n              const worktreeGuardMessage = cappycloudValidateToolScope(tool.name, input, grpcAllowedWorktree)\\n              if (worktreeGuardMessage) {\\n                console.warn('[grpc] worktree guard denied')\\n                return {\\n                  behavior: 'deny' as const,\\n                  message: worktreeGuardMessage,\\n                  decisionReason: {\\n                    type: 'other' as const,\\n                    reason: worktreeGuardMessage,\\n                  },\\n                }\\n              }\\n              \\/\\/ Notify client of the tool call first/" src/grpc/server.ts \
    && perl -0pi -e "s/call\\.write\\(\\{\\n                tool_start:/call.write({\\n                request_id: currentRequestId,\\n                tool_start:/g; s/call\\.write\\(\\{\\n                action_required:/call.write({\\n                request_id: currentRequestId,\\n                action_required:/g; s/call\\.write\\(\\{\\n                  text_chunk:/call.write({\\n                  request_id: currentRequestId,\\n                  text_chunk:/g; s/call\\.write\\(\\{\\n                      tool_result:/call.write({\\n                      request_id: currentRequestId,\\n                      tool_result:/g; s/call\\.write\\(\\{\\n              done:/call.write({\\n              request_id: currentRequestId,\\n              done:/g; s/call\\.write\\(\\{\\n          error:/call.write({\\n          request_id: currentRequestId,\\n          error:/g" src/grpc/server.ts \
    && perl -0pi -e "s/\\n\\n              \\/\\/ Ask user for permission/\\n\\n              const permissionDecision = cappycloudPermissionDecision(grpcPermissionMode, tool.name)\\n              if (permissionDecision) {\\n                if (permissionDecision.behavior === 'allow') {\\n                  return { behavior: 'allow' as const }\\n                }\\n                const permissionMessage = permissionDecision.message ?? 'Tool blocked by session permission mode.'\\n                console.warn('[grpc] permission denied')\\n                return {\\n                  behavior: 'deny' as const,\\n                  message: permissionMessage,\\n                  decisionReason: {\\n                    type: 'other' as const,\\n                    reason: permissionMessage,\\n                  },\\n                }\\n              }\\n\\n              \\/\\/ Ask user for permission/" src/grpc/server.ts \
    && perl -0pi -e "s/const generator = engine\\.submitMessage\\(req\\.message\\)/let promptInput: any = req.message\\n          if (Array.isArray(req.attachments) \\&\\& req.attachments.length > 0) {\\n            const imageBlocks = req.attachments.map((att: any) => ({\\n              type: 'image',\\n              source: {\\n                type: 'base64',\\n                media_type: att.mime_type,\\n                data: Buffer.from(att.data).toString('base64'),\\n              },\\n            }))\\n            promptInput = [...imageBlocks, { type: 'text', text: req.message }]\\n          }\\n          const generator = engine.submitMessage(promptInput)/" src/grpc/server.ts \
    && perl -0pi -e "s/output: outputStr,/output: Buffer.from(outputStr, 'utf8'),/g; s/\\n            \\/\\/ Save messages for multi-turn context in subsequent requests\\n            previousMessages = \\[\\.\\.\\.engine\\.getMessages\\(\\)\\]\\n\\n            \\/\\/ Persist to session store for cross-stream resumption\\n            if \\(sessionId\\) \\{\\n              if \\(!this\\.sessions\\.has\\(sessionId\\) \\&\\& this\\.sessions\\.size >= MAX_SESSIONS\\) \\{\\n                \\/\\/ Evict oldest session \\(Map preserves insertion order\\)\\n                this\\.sessions\\.delete\\(this\\.sessions\\.keys\\(\\)\\.next\\(\\)\\.value\\)\\n              \\}\\n              this\\.sessions\\.set\\(sessionId, previousMessages\\)\\n            \\}/\\n            \\/\\/ Do not persist OpenClaude messages across streams. CappyCloud sends authorized history./" src/grpc/server.ts \
    && perl -0pi -e "s/function cappycloudPermissionDecision/function cappycloudGrpcString(value: unknown): string {\\n  return Buffer.from(String(value ?? ''), 'utf8').toString('utf8')\\n}\\n\\nfunction cappycloudPermissionDecision/" src/grpc/server.ts \
    && perl -0pi -e "s/tool_name: tool\\.name,/tool_name: cappycloudGrpcString(tool.name),/g; s/arguments_json: JSON\\.stringify\\(input\\),/arguments_json: cappycloudGrpcString(JSON.stringify(input)),/g; s/tool_use_id: toolUseID/tool_use_id: cappycloudGrpcString(toolUseID)/g; s/prompt_id: promptId,/prompt_id: cappycloudGrpcString(promptId),/g; s/question,/question: cappycloudGrpcString(question),/g; s/text: msg\\.event\\.delta\\.text/text: cappycloudGrpcString(msg.event.delta.text)/g; s/tool_name: toolNameById\\.get\\(block\\.tool_use_id\\) \\?\\? block\\.tool_use_id,/tool_name: cappycloudGrpcString(toolNameById.get(block.tool_use_id) ?? block.tool_use_id),/g; s/tool_use_id: block\\.tool_use_id,/tool_use_id: cappycloudGrpcString(block.tool_use_id),/g; s/full_text: fullText,/full_text: cappycloudGrpcString(fullText),/g; s/message: err\\.message \\|\\| \"Internal server error\",/message: cappycloudGrpcString(err.message || \"Internal server error\"),/g" src/grpc/server.ts \
    && perl -0pi -e "s/type: 'CONFIRM_COMMAND'/type: 1/g; s/if \(reply\.toLowerCase\(\) === 'yes' \|\| reply\.toLowerCase\(\) === 'y'\) \{/if (['yes', 'y', 'sim', 's'].includes(reply.toLowerCase().trim())) {/g" src/grpc/server.ts \
    && sed -i 's/^detectStubLeaks()$/setImmediate(() => detectStubLeaks())/' src/entrypoints/sdk/index.ts \
    && node /tmp/patch_openclaude_grpc_v024.js \
    && rm -f /tmp/grep-tool-n-alias.patch \
            /tmp/multimodal-proto.patch /tmp/multimodal-grpc-handler.patch \
            /tmp/read-empty-pages.patch /tmp/patch_openclaude_grpc_v024.js \
            /tmp/cappycloud_grpc_helpers_v024.ts /tmp/cappycloud_grpc_diagnostics_v024.ts \
    && bun install \
    && bun run build

# signoz-mcp-server (binario Go, modo stdio)
RUN ARCH=$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/') \
    && mkdir /tmp/signoz-extract \
    && curl -fsSL \
       "https://github.com/SigNoz/signoz-mcp-server/releases/latest/download/signoz-mcp-server_linux_${ARCH}.tar.gz" \
       | tar xz -C /tmp/signoz-extract \
    && find /tmp/signoz-extract -maxdepth 3 \( -name 'signoz-mcp-server' -o -name 'server' \) -type f \
       | head -1 | xargs -I{} install -m 755 {} /usr/local/bin/signoz-mcp-server \
    && rm -rf /tmp/signoz-extract

# GitHub MCP server, official Go binary in stdio mode.
COPY --from=github-mcp-builder /out/github-mcp-server /usr/local/bin/github-mcp-server
COPY services/sandbox/github_mcp_server_wrapper.sh /usr/local/bin/github-mcp-server-wrapper
RUN chmod +x /usr/local/bin/github-mcp-server /usr/local/bin/github-mcp-server-wrapper

RUN mkdir -p /repos
WORKDIR /repos

# Agent instructions injected into every workspace.
COPY sandbox/CLAUDE.md /app/CLAUDE.md
COPY sandbox/skills /app/sandbox/skills

# Entrypoints e scripts
COPY services/sandbox/env_init.sh /env_init.sh
COPY services/sandbox/session_start.sh /session_start.sh
COPY services/sandbox/session_server.js /session_server.js
COPY services/sandbox/git_handlers.js /git_handlers.js
COPY services/sandbox/globals_handler.js /globals_handler.js
COPY services/sandbox/mcp_handler.js /mcp_handler.js
COPY services/sandbox/confluence_auth.js /confluence_auth.js
COPY services/sandbox/confluence_handler.js /confluence_handler.js
COPY services/sandbox/repo_handlers.js /repo_handlers.js
COPY services/sandbox/runtime_handler.js /runtime_handler.js
COPY services/sandbox/task_handler.js /task_handler.js
COPY services/sandbox/worktree_handlers.js /worktree_handlers.js
COPY services/sandbox/confluence_mcp_lib.py /usr/local/bin/confluence_mcp_lib.py
COPY services/sandbox/confluence_mcp_server.py /usr/local/bin/confluence-mcp-server
RUN sed -i 's/\r//' /env_init.sh /session_start.sh \
    && chmod +x /env_init.sh /session_start.sh /usr/local/bin/confluence-mcp-server

ENTRYPOINT ["/env_init.sh"]
