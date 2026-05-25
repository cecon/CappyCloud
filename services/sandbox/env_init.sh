#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# CappyCloud Sandbox — Persistent Environment Init
#
# Roda quando o container sandbox sobe. O diretório /repos é um
# volume Docker persistente: repos sobrevivem a restarts/rebuilds.
#
# O que faz:
#   1. Configura git auth para Azure DevOps (DEVOPS_TOKEN) e/ou
#      GitHub (GITHUB_TOKEN) — cada um só se a variável estiver definida.
#   2. Clona repos listados em WORKSPACE_REPOS se ainda não existirem
#      no volume; se já existirem, faz git fetch para atualizar.
#   3. Aplica patch no context-window do openclaude para modelos OpenRouter.
#   4. Sobe session_server.js (HTTP :8080) em background.
#   5. Executa o servidor gRPC do openclaude (processo principal).
# ──────────────────────────────────────────────────────────────
set -euo pipefail

: "${OPENAI_API_KEY:?OPENAI_API_KEY is required}"

OPENAI_BASE_URL="${OPENAI_BASE_URL:-https://openrouter.ai/api/v1}"
OPENAI_MODEL="${OPENAI_MODEL:-anthropic/claude-3.5-sonnet}"
CLAUDE_CODE_USE_OPENAI="${CLAUDE_CODE_USE_OPENAI:-1}"
GRPC_HOST="${GRPC_HOST:-0.0.0.0}"
GRPC_PORT="${GRPC_PORT:-50051}"
SESSION_SERVER_PORT="${SESSION_SERVER_PORT:-8080}"
OPENCLAUDE_AUTO_APPROVE="${OPENCLAUDE_AUTO_APPROVE:-1}"
WORKSPACE_REPOS="${WORKSPACE_REPOS:-}"
WORKSPACE_BRANCH="${WORKSPACE_BRANCH:-main}"
DEVOPS_TOKEN="${DEVOPS_TOKEN:-}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"

# ── Configure openclaude ──────────────────────────────────────
mkdir -p ~/.claude
cat > ~/.claude/settings.json <<EOF
{
  "apiKeyHelper": null,
  "autoUpdaterStatus": "disabled"
}
EOF

echo "Provider: OpenRouter  model=${OPENAI_MODEL}"

# ── Git global identity ───────────────────────────────────────
git config --global user.email "${GIT_USER_EMAIL:-agent@cappycloud.local}"
git config --global user.name "${GIT_USER_NAME:-CappyCloud Agent}"

# ── Git authentication (por provedor) ────────────────────────
if [ -n "${DEVOPS_TOKEN}" ]; then
    git config --global url."https://pat:${DEVOPS_TOKEN}@dev.azure.com".insteadOf \
        "https://dev.azure.com"
    echo "Git auth: Azure DevOps configurado."
fi

if [ -n "${GITHUB_TOKEN}" ]; then
    git config --global url."https://x-token:${GITHUB_TOKEN}@github.com".insteadOf \
        "https://github.com"
    echo "Git auth: GitHub configurado."

    # Configura gh CLI para uso pelo agente
    echo "${GITHUB_TOKEN}" | gh auth login --with-token 2>/dev/null || true
fi

if [ -n "${DEVOPS_TOKEN}" ]; then
    # Configura az CLI para uso pelo agente
    az devops configure --defaults organization="" 2>/dev/null || true
    export AZURE_DEVOPS_EXT_PAT="${DEVOPS_TOKEN}"
fi

# ── Função: clonar ou atualizar um repo ──────────────────────
clone_or_update_repo() {
    local repo_url="$1"
    local slug
    slug=$(basename "${repo_url}" | sed 's/\.git$//')
    local repo_dir="/repos/${slug}"

    echo ""
    echo "==> Repo: ${slug}  (${repo_url})"
    mkdir -p "${repo_dir}"

    # Monta URL autenticada
    local auth_url="${repo_url}"
    if [ -n "${DEVOPS_TOKEN}" ]; then
        auth_url=$(echo "${auth_url}" | \
            sed "s|https://dev.azure.com|https://pat:${DEVOPS_TOKEN}@dev.azure.com|")
    fi
    if [ -n "${GITHUB_TOKEN}" ]; then
        auth_url=$(echo "${auth_url}" | \
            sed "s|https://github.com|https://x-token:${GITHUB_TOKEN}@github.com|")
    fi

    if [ -d "${repo_dir}/.git" ]; then
        # Volume já tem o repo — só atualiza
        echo "    Volume existente — atualizando (git fetch)..."
        local default_branch
        default_branch=$(git -C "${repo_dir}" remote show origin 2>/dev/null \
            | sed -n 's/.*HEAD branch: //p' | tr -d '[:space:]') || true
        default_branch="${default_branch:-${WORKSPACE_BRANCH}}"
        git -C "${repo_dir}" fetch origin "${default_branch}" 2>&1 \
            && git -C "${repo_dir}" checkout "${default_branch}" 2>/dev/null \
            && git -C "${repo_dir}" merge --ff-only "origin/${default_branch}" 2>&1 \
            || echo "    WARNING: git update falhou — continuando com código existente."
    else
        # Volume vazio ou repo ausente — clona
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
            echo "    WARNING: clone falhou — inicializando workspace vazio."
            git -C "${repo_dir}" init -b main 2>/dev/null || git -C "${repo_dir}" init
            git -C "${repo_dir}" commit --allow-empty -m "init" 2>/dev/null || true
        fi
    fi

    # Garante pelo menos um commit para worktrees funcionarem
    if ! git -C "${repo_dir}" rev-parse HEAD >/dev/null 2>&1; then
        git -C "${repo_dir}" commit --allow-empty -m "init"
    fi

    # Não copiamos CLAUDE.md para o clone principal — o repo pode ter o seu
    # próprio. A injeção só acontece nos worktrees de sessão (session_start.sh)
    # e mesmo aí só quando o repo não tem CLAUDE.md/AGENTS.md.

    mkdir -p "${repo_dir}/sessions"
}

# Repos são clonados via watchdog (DB → /repos/clone). Sandbox inicia sem pre-clone.
echo "Sandbox ready — repos will be cloned via watchdog (sandbox_sync_queue)."

# ── Patch openclaude: context-window para modelos OpenRouter ─
_TS=/openclaude/src/utils/model/openaiContextWindows.ts
if [ -f "$_TS" ]; then
    node - "$_TS" << 'PATCH_EOF'
const fs = require('fs');
const file = process.argv[2];
let c = fs.readFileSync(file, 'utf8');
const needle = "  // Groq (fast inference)\n  'llama-3.3-70b-versatile'";
const insert = [
  "  // OpenRouter-namespaced models",
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
  "  'deepseek/deepseek-v3':         65_536,",
  "  'deepseek/deepseek-v3-0324':    65_536,",
  "  'deepseek/deepseek-v3.2':       65_536,",
  "  'deepseek/deepseek-chat':       65_536,",
  "  'deepseek/deepseek-r1':         65_536,",
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

# ── Patch openclaude OpenAI shim: usage real em stream ────────
# Alguns gateways OpenAI-compatible (incluindo OpenRouter em rotas com tools)
# enviam o bloco `usage` em chunk separado do `finish_reason`. O QueryEngine só
# acumula usage recebido antes de `message_stop`; portanto guardamos o último
# usage real recebido no stream e emitimos um `message_delta` final antes do stop
# quando o fluxo normal não o emitiu.
_OPENAI_SHIM_TS=/openclaude/src/services/api/openaiShim.ts
if [ -f "$_OPENAI_SHIM_TS" ]; then
    node - "$_OPENAI_SHIM_TS" << 'PATCH_EOF'
const fs = require('fs');
const file = process.argv[2];
let c = fs.readFileSync(file, 'utf8');
if (c.includes('CappyCloud final stream usage')) {
  console.log('[env_init] OpenAI shim usage patch: already present.');
  process.exit(0);
}
const stateNeedle = "  let hasEmittedFinalUsage = false\n  let hasProcessedFinishReason = false";
const stateReplacement = "  let hasEmittedFinalUsage = false\n  let pendingFinalUsage: Partial<AnthropicUsage> | undefined\n  let hasProcessedFinishReason = false";
if (c.includes(stateNeedle)) {
  c = c.replace(stateNeedle, stateReplacement);
} else {
  console.log('[env_init] OpenAI shim usage patch: state needle not found, skipping.');
  process.exit(0);
}
const chunkNeedle = "      const chunkUsage = convertChunkUsage(chunk.usage)\n\n      for (const choice of chunk.choices ?? []) {";
const chunkReplacement = "      const chunkUsage = convertChunkUsage(chunk.usage)\n      if (chunkUsage) {\n        // CappyCloud final stream usage: preserve real provider usage even when it arrives in a standalone chunk.\n        pendingFinalUsage = chunkUsage\n      }\n\n      for (const choice of chunk.choices ?? []) {";
if (c.includes(chunkNeedle)) {
  c = c.replace(chunkNeedle, chunkReplacement);
} else {
  console.log('[env_init] OpenAI shim usage patch: chunk needle not found, skipping.');
  process.exit(0);
}
const stopNeedle = "  yield { type: 'message_stop' }";
const stopReplacement = "  if (!hasEmittedFinalUsage && pendingFinalUsage) {\n    yield {\n      type: 'message_delta',\n      delta: { stop_reason: lastStopReason ?? 'end_turn', stop_sequence: null },\n      usage: pendingFinalUsage,\n    }\n    hasEmittedFinalUsage = true\n  }\n\n  yield { type: 'message_stop' }";
if (c.includes(stopNeedle)) {
  c = c.replace(stopNeedle, stopReplacement);
} else {
  console.log('[env_init] OpenAI shim usage patch: stop needle not found, skipping.');
  process.exit(0);
}
fs.writeFileSync(file, c);
console.log('[env_init] OpenAI shim usage patch applied.');
PATCH_EOF
fi

# ── Patch openclaude OpenAI shim: Azure AI Foundry OpenAI v1 ─
# O endpoint novo do Azure AI Foundry (`...services.ai.azure.com/openai/v1`)
# segue o cliente OpenAI oficial: base_url=/openai/v1 e model=deployment.
# O openclaude upstream também suporta Azure antigo, mas transforma qualquer
# host Azure em `/openai/deployments/{model}/chat/completions?api-version=...`.
# Para o v1, preservamos `/openai/v1/chat/completions` e auth Bearer.
if [ -f "$_OPENAI_SHIM_TS" ]; then
    node - "$_OPENAI_SHIM_TS" << 'PATCH_EOF'
const fs = require('fs');
const file = process.argv[2];
let c = fs.readFileSync(file, 'utf8');
if (c.includes('CappyCloud Azure AI Foundry v1')) {
  console.log('[env_init] Azure v1 shim patch: already present.');
  process.exit(0);
}
const azureFlagNeedle = "    let isBankr = false\n    try {";
const azureFlagReplacement = "    let isAzureOpenAIV1 = false\n    try {\n      const { pathname } = new URL(request.baseUrl)\n      isAzureOpenAIV1 = isAzure && /\\/openai\\/v1\\/?$/i.test(pathname)\n    } catch { /* malformed URL — not Azure OpenAI v1 */ }\n\n    let isBankr = false\n    try {";
if (c.includes(azureFlagNeedle)) {
  c = c.replace(azureFlagNeedle, azureFlagReplacement);
} else {
  console.log('[env_init] Azure v1 shim patch: flag needle not found, skipping.');
  process.exit(0);
}
const azureAuthNeedle = "      } else if (isAzure) {\n        // Azure uses api-key header instead of Bearer token\n        headers['api-key'] = authValue";
const azureAuthReplacement = "      } else if (isAzure && !isAzureOpenAIV1) {\n        // Azure uses api-key header instead of Bearer token for legacy deployment endpoints.\n        headers['api-key'] = authValue";
if (c.includes(azureAuthNeedle)) {
  c = c.replace(azureAuthNeedle, azureAuthReplacement);
} else {
  console.log('[env_init] Azure v1 shim patch: auth needle not found, skipping.');
  process.exit(0);
}
const azureUrlNeedle = "      if (isAzure) {\n        const apiVersion = process.env.AZURE_OPENAI_API_VERSION ?? '2024-12-01-preview'";
const azureUrlReplacement = "      if (isAzure) {\n        const normalizedBaseForV1 = baseUrl.replace(/\\/+$/, '')\n        if (/\\/openai\\/v1$/i.test(normalizedBaseForV1)) {\n          // CappyCloud Azure AI Foundry v1: OpenAI-compatible path, model is the deployment name.\n          return `${normalizedBaseForV1}/chat/completions`\n        }\n        const apiVersion = process.env.AZURE_OPENAI_API_VERSION ?? '2024-12-01-preview'";
if (c.includes(azureUrlNeedle)) {
  c = c.replace(azureUrlNeedle, azureUrlReplacement);
} else {
  console.log('[env_init] Azure v1 shim patch: URL needle not found, skipping.');
  process.exit(0);
}
fs.writeFileSync(file, c);
console.log('[env_init] Azure v1 shim patch applied.');
PATCH_EOF
fi

# ── Patch openclaude gRPC: modelo dinâmico por request ───────
# O QueryEngine recebe `userSpecifiedModel`, mas partes do shim OpenAI ainda
# consultam process.env.OPENAI_MODEL. Em modo gRPC/headless, alinhar a env ao
# ChatRequest.model garante que o modelo escolhido na UI chegue ao OpenRouter.
_GRPC_TS=/openclaude/src/grpc/server.ts
if [ -f "$_GRPC_TS" ]; then
    node - "$_GRPC_TS" << 'PATCH_EOF'
const fs = require('fs');
const file = process.argv[2];
let c = fs.readFileSync(file, 'utf8');
if (c.includes('CappyCloud dynamic model override') && c.includes('CappyCloud provider override') && c.includes('CappyCloud billable usage')) {
  console.log('[env_init] gRPC dynamic model patch: already present.');
  process.exit(0);
}
const importNeedle = "import { QueryEngine } from '../QueryEngine.js'";
if (c.includes(importNeedle) && !c.includes("from '../cost-tracker.js'")) {
  c = c.replace(importNeedle, importNeedle + "\nimport { getModelUsage } from '../cost-tracker.js'");
}
const needle = "          const req = clientMessage.request\n          sessionId = req.session_id || ''";
const replacement = "          const req = clientMessage.request\n          const requestedModel = String(req.model || '').trim()\n          const requestedProviderBaseUrl = String(req.provider_base_url || '').trim().replace(/\\/+$/, '')\n          const requestedProviderApiKey = String(req.provider_api_key || '').trim()\n          const requestedProviderApiFormat = String(req.provider_api_format || '').trim()\n          const previousOpenAIModel = process.env.OPENAI_MODEL\n          const previousOpenAIBaseUrl = process.env.OPENAI_BASE_URL\n          const previousOpenAIApiKey = process.env.OPENAI_API_KEY\n          const previousOpenAIApiFormat = process.env.OPENAI_API_FORMAT\n          if (requestedModel) {\n            // CappyCloud dynamic model override: OpenAI shim fallback paths read OPENAI_MODEL.\n            process.env.OPENAI_MODEL = requestedModel\n            console.log(`[grpc] dynamic model override: ${requestedModel}`)\n          }\n          if (requestedProviderBaseUrl && requestedProviderApiKey) {\n            // CappyCloud provider override: route this request to the selected provider without logging secrets.\n            process.env.OPENAI_BASE_URL = requestedProviderBaseUrl\n            process.env.OPENAI_API_KEY = requestedProviderApiKey\n            if (requestedProviderApiFormat === 'responses' || requestedProviderApiFormat === 'chat_completions') {\n              process.env.OPENAI_API_FORMAT = requestedProviderApiFormat\n            }\n            console.log(`[grpc] provider override: ${requestedProviderBaseUrl} format=${process.env.OPENAI_API_FORMAT || 'chat_completions'}`)\n          }\n          sessionId = req.session_id || ''";
if (c.includes(needle)) {
  c = c.replace(needle, replacement);
} else if (!c.includes('CappyCloud dynamic model override')) {
  console.log('[env_init] gRPC dynamic model patch: needle not found, skipping.');
  process.exit(0);
}
const providerVarsNeedle = "          const requestedModel = String(req.model || '').trim()\n          const previousOpenAIModel = process.env.OPENAI_MODEL\n          if (requestedModel) {";
const providerVarsReplacement = "          const requestedModel = String(req.model || '').trim()\n          const requestedProviderBaseUrl = String(req.provider_base_url || '').trim().replace(/\\/+$/, '')\n          const requestedProviderApiKey = String(req.provider_api_key || '').trim()\n          const requestedProviderApiFormat = String(req.provider_api_format || '').trim()\n          const previousOpenAIModel = process.env.OPENAI_MODEL\n          const previousOpenAIBaseUrl = process.env.OPENAI_BASE_URL\n          const previousOpenAIApiKey = process.env.OPENAI_API_KEY\n          const previousOpenAIApiFormat = process.env.OPENAI_API_FORMAT\n          if (requestedModel) {";
if (!c.includes('CappyCloud provider override') && c.includes(providerVarsNeedle)) {
  c = c.replace(providerVarsNeedle, providerVarsReplacement);
}
const providerBlockNeedle = "          if (requestedModel) {\n            // CappyCloud dynamic model override: OpenAI shim fallback paths read OPENAI_MODEL.\n            process.env.OPENAI_MODEL = requestedModel\n            console.log(`[grpc] dynamic model override: ${requestedModel}`)\n          }\n          sessionId = req.session_id || ''";
const providerBlockReplacement = "          if (requestedModel) {\n            // CappyCloud dynamic model override: OpenAI shim fallback paths read OPENAI_MODEL.\n            process.env.OPENAI_MODEL = requestedModel\n            console.log(`[grpc] dynamic model override: ${requestedModel}`)\n          }\n          if (requestedProviderBaseUrl && requestedProviderApiKey) {\n            // CappyCloud provider override: route this request to the selected provider without logging secrets.\n            process.env.OPENAI_BASE_URL = requestedProviderBaseUrl\n            process.env.OPENAI_API_KEY = requestedProviderApiKey\n            if (requestedProviderApiFormat === 'responses' || requestedProviderApiFormat === 'chat_completions') {\n              process.env.OPENAI_API_FORMAT = requestedProviderApiFormat\n            }\n            console.log(`[grpc] provider override: ${requestedProviderBaseUrl} format=${process.env.OPENAI_API_FORMAT || 'chat_completions'}`)\n          }\n          sessionId = req.session_id || ''";
if (!c.includes('CappyCloud provider override') && c.includes(providerBlockNeedle)) {
  c = c.replace(providerBlockNeedle, providerBlockReplacement);
}
const usageNeedle = "          // Track accumulated response data for FinalResponse\n          let fullText = ''";
const usageReplacement = "          // Track accumulated response data for FinalResponse\n          const usageBefore = JSON.parse(JSON.stringify(getModelUsage()))\n          let fullText = ''";
if (c.includes(usageNeedle) && !c.includes('const usageBefore = JSON.parse')) {
  c = c.replace(usageNeedle, usageReplacement);
}
const resultUsageNeedle = "                promptTokens = msg.usage?.input_tokens ?? 0\n                completionTokens = msg.usage?.output_tokens ?? 0";
const resultUsageReplacement = "                const freshInputTokens = msg.usage?.input_tokens ?? 0\n                const cacheReadTokens = msg.usage?.cache_read_input_tokens ?? 0\n                const cacheCreationTokens = msg.usage?.cache_creation_input_tokens ?? 0\n                // CappyCloud billable usage: OpenRouter's Input column includes fresh + cache tokens.\n                promptTokens = freshInputTokens + cacheReadTokens + cacheCreationTokens\n                completionTokens = msg.usage?.output_tokens ?? 0";
if (c.includes(resultUsageNeedle)) {
  c = c.replace(resultUsageNeedle, resultUsageReplacement);
} else if (!c.includes('CappyCloud billable usage')) {
  console.log('[env_init] gRPC result usage patch: needle not found, skipping result cache totals.');
}
const doneNeedle = "            call.write({\n              done: {\n                full_text: fullText,\n                prompt_tokens: promptTokens,\n                completion_tokens: completionTokens\n              }\n            })";
const doneReplacement = "            const usageAfter = getModelUsage()\n            let accumulatedInputTokens = 0\n            let accumulatedOutputTokens = 0\n            for (const [modelName, usage] of Object.entries(usageAfter)) {\n              const before = usageBefore[modelName] || {}\n              const freshDelta = Math.max(0, (usage.inputTokens || 0) - (before.inputTokens || 0))\n              const cacheReadDelta = Math.max(0, (usage.cacheReadInputTokens || 0) - (before.cacheReadInputTokens || 0))\n              const cacheCreationDelta = Math.max(0, (usage.cacheCreationInputTokens || 0) - (before.cacheCreationInputTokens || 0))\n              // CappyCloud billable usage: OpenRouter bills every tool-loop API call and its Input column includes cache tokens.\n              accumulatedInputTokens += freshDelta + cacheReadDelta + cacheCreationDelta\n              accumulatedOutputTokens += Math.max(0, (usage.outputTokens || 0) - (before.outputTokens || 0))\n            }\n            if (accumulatedInputTokens > 0 || accumulatedOutputTokens > 0) {\n              promptTokens = accumulatedInputTokens\n              completionTokens = accumulatedOutputTokens\n            }\n            call.write({\n              done: {\n                full_text: fullText,\n                prompt_tokens: promptTokens,\n                completion_tokens: completionTokens\n              }\n            })";
if (c.includes(doneNeedle)) {
  c = c.replace(doneNeedle, doneReplacement);
} else if (!c.includes('CappyCloud billable usage')) {
  console.log('[env_init] gRPC accumulated usage patch: needle not found, skipping usage totals.');
}
if (c.includes('CappyCloud accumulated usage: OpenRouter bills every tool-loop API call, not only the final result.')) {
  c = c.replace(
    "              // CappyCloud accumulated usage: OpenRouter bills every tool-loop API call, not only the final result.\n              accumulatedInputTokens += Math.max(0, (usage.inputTokens || 0) - (before.inputTokens || 0))\n              accumulatedOutputTokens += Math.max(0, (usage.outputTokens || 0) - (before.outputTokens || 0))",
    "              const freshDelta = Math.max(0, (usage.inputTokens || 0) - (before.inputTokens || 0))\n              const cacheReadDelta = Math.max(0, (usage.cacheReadInputTokens || 0) - (before.cacheReadInputTokens || 0))\n              const cacheCreationDelta = Math.max(0, (usage.cacheCreationInputTokens || 0) - (before.cacheCreationInputTokens || 0))\n              // CappyCloud billable usage: OpenRouter bills every tool-loop API call and its Input column includes cache tokens.\n              accumulatedInputTokens += freshDelta + cacheReadDelta + cacheCreationDelta\n              accumulatedOutputTokens += Math.max(0, (usage.outputTokens || 0) - (before.outputTokens || 0))"
  );
}
const resetNeedle = "          engine = null\n\n        } else if (clientMessage.input) {";
const resetReplacement = "          engine = null\n          if (typeof previousOpenAIModel === 'string') {\n            process.env.OPENAI_MODEL = previousOpenAIModel\n          } else {\n            delete process.env.OPENAI_MODEL\n          }\n          if (typeof previousOpenAIBaseUrl === 'string') {\n            process.env.OPENAI_BASE_URL = previousOpenAIBaseUrl\n          } else {\n            delete process.env.OPENAI_BASE_URL\n          }\n          if (typeof previousOpenAIApiKey === 'string') {\n            process.env.OPENAI_API_KEY = previousOpenAIApiKey\n          } else {\n            delete process.env.OPENAI_API_KEY\n          }\n          if (typeof previousOpenAIApiFormat === 'string') {\n            process.env.OPENAI_API_FORMAT = previousOpenAIApiFormat\n          } else {\n            delete process.env.OPENAI_API_FORMAT\n          }\n\n        } else if (clientMessage.input) {";
if (!c.includes(resetNeedle)) {
  console.log('[env_init] gRPC dynamic model reset patch: needle not found, skipping reset.');
} else {
  c = c.replace(resetNeedle, resetReplacement);
}
const dynamicResetNeedle = "          engine = null\n          if (typeof previousOpenAIModel === 'string') {\n            process.env.OPENAI_MODEL = previousOpenAIModel\n          } else {\n            delete process.env.OPENAI_MODEL\n          }\n\n        } else if (clientMessage.input) {";
if (!c.includes('process.env.OPENAI_BASE_URL = previousOpenAIBaseUrl') && c.includes(dynamicResetNeedle)) {
  c = c.replace(dynamicResetNeedle, resetReplacement);
}
fs.writeFileSync(file, c);
console.log('[env_init] gRPC dynamic model patch applied.');
PATCH_EOF
fi

# ── Exporta vars para openclaude e session_server ────────────
export CLAUDE_CODE_USE_OPENAI="${CLAUDE_CODE_USE_OPENAI}"
export OPENAI_BASE_URL="${OPENAI_BASE_URL}"
export OPENAI_API_KEY="${OPENAI_API_KEY}"
export OPENAI_MODEL="${OPENAI_MODEL}"
export GRPC_HOST="${GRPC_HOST}"
export GRPC_PORT="${GRPC_PORT}"
export OPENCLAUDE_AUTO_APPROVE="${OPENCLAUDE_AUTO_APPROVE}"
export DEVOPS_TOKEN="${DEVOPS_TOKEN:-}"
export GITHUB_TOKEN="${GITHUB_TOKEN:-}"

# ── Sobe o session server em background ──────────────────────
echo ""
echo "Starting session server on :${SESSION_SERVER_PORT}..."
SESSION_SERVER_PORT="${SESSION_SERVER_PORT}" node /session_server.js &
SESSION_SERVER_PID=$!
echo "Session server PID: ${SESSION_SERVER_PID}"

# ── Inicia o servidor gRPC do openclaude (processo principal) ─
echo "Starting openclaude gRPC server on ${GRPC_HOST}:${GRPC_PORT}..."
cd /openclaude
exec npm run dev:grpc
