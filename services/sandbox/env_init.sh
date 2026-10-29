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
#   3. Aplica patches no openclaude (Azure AI Foundry v1; modelo, provider e
#      usage por request no gRPC).
#   4. Sobe session_server.js (HTTP :8080) em background.
#   5. Executa o servidor gRPC do openclaude (processo principal).
# ──────────────────────────────────────────────────────────────
set -euo pipefail

OPENAI_BASE_URL="${OPENAI_BASE_URL:-https://openrouter.ai/api/v1}"
# OpenClaude initializes its provider registry before CappyCloud injects
# the per-request provider credentials. Keep startup independent from
# OPENGATEWAY_API_KEY; real requests replace this with ChatRequest.provider_api_key.
# CLAUDE_CODE_USE_OPENAI=1 + OPENAI_BASE_URL also count as a concrete provider
# selection upstream, so OpenClaude never falls back to the Opengateway profile.
OPENAI_API_KEY="${OPENAI_API_KEY:-cappycloud-runtime-bootstrap-key}"
OPENAI_MODEL="${OPENAI_MODEL:-anthropic/claude-3.5-sonnet}"
CLAUDE_CODE_USE_OPENAI="${CLAUDE_CODE_USE_OPENAI:-1}"
GRPC_HOST="${GRPC_HOST:-0.0.0.0}"
GRPC_PORT="${GRPC_PORT:-50051}"
SESSION_SERVER_PORT="${SESSION_SERVER_PORT:-8080}"
WORKSPACE_REPOS="${WORKSPACE_REPOS:-}"
WORKSPACE_BRANCH="${WORKSPACE_BRANCH:-main}"
DEVOPS_TOKEN="${DEVOPS_TOKEN:-}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"

# ── Configure openclaude ──────────────────────────────────────
# ~/.claude pode ser um volume persistente (CLAUDE_CONFIG_DIR) com o login do
# Claude CLI: só atualiza as chaves do CappyCloud, preservando o resto.
mkdir -p ~/.claude
node - <<'JSEOF'
const fs = require('fs')
const file = `${process.env.HOME || '/root'}/.claude/settings.json`
let current = {}
try { current = JSON.parse(fs.readFileSync(file, 'utf8')) } catch {}
// Sem apiKeyHelper: o openclaude recebe a chave por request e o Claude CLI usa o `claude login`.
delete current.apiKeyHelper
current.autoUpdaterStatus = 'disabled'
fs.writeFileSync(file, JSON.stringify(current, null, 2), 'utf8')
JSEOF

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

# ── Patch openclaude OpenAI shim: Azure AI Foundry OpenAI v1 ─
# O endpoint novo do Azure AI Foundry (`...services.ai.azure.com/openai/v1`)
# segue o cliente OpenAI oficial: base_url=/openai/v1 e model=deployment.
# O openclaude upstream (até 0.32.0) transforma qualquer host Azure em
# `/openai/deployments/{model}/chat/completions?api-version=...` com header
# `api-key`, o que não serve para os deployments não-OpenAI do Foundry
# (DeepSeek, Kimi...). Para o v1, preservamos `/openai/v1/chat/completions`
# e auth Bearer.
_OPENAI_REQUEST_EXECUTOR_TS=/openclaude/src/services/api/openaiShim/requestExecutor.ts
if [ -f "$_OPENAI_REQUEST_EXECUTOR_TS" ]; then
    node - "$_OPENAI_REQUEST_EXECUTOR_TS" << 'PATCH_EOF'
const fs = require('fs');
const file = process.argv[2];
let c = fs.readFileSync(file, 'utf8');
if (c.includes('CappyCloud Azure AI Foundry v1')) {
  console.log('[env_init] Azure v1 shim patch: already present.');
  process.exit(0);
}
const steps = [
  {
    name: 'flag',
    needle: "  const isAzure = isAzureStyleBaseUrl(request.baseUrl, requestProcessEnv)\n",
    replacement: "  const isAzure = isAzureStyleBaseUrl(request.baseUrl, requestProcessEnv)\n  let isAzureOpenAIV1 = false\n  try {\n    isAzureOpenAIV1 =\n      isAzure && /\\/openai\\/v1\\/?$/i.test(new URL(request.baseUrl).pathname)\n  } catch {\n    /* malformed URL — not Azure OpenAI v1 */\n  }\n",
  },
  {
    name: 'auth',
    needle: "      } else if (isAzure) {\n        // Azure uses api-key header instead of Bearer token\n        headers['api-key'] = authValue",
    replacement: "      } else if (isAzure && !isAzureOpenAIV1) {\n        // Azure uses api-key header instead of Bearer token for legacy deployment endpoints.\n        headers['api-key'] = authValue",
  },
  {
    name: 'URL',
    needle: "      // If base URL already contains /deployments/, use it as-is with api-version.\n",
    replacement: "      if (/\\/openai\\/v1$/i.test(normalizedBaseUrl)) {\n        // CappyCloud Azure AI Foundry v1: OpenAI-compatible path, model is the deployment name.\n        return `${normalizedBaseUrl}/chat/completions`\n      }\n\n      // If base URL already contains /deployments/, use it as-is with api-version.\n",
  },
];
// Aplica tudo ou nada: um patch parcial misturaria auth Bearer com URL legada.
for (const step of steps) {
  if (!c.includes(step.needle)) {
    console.log(`[env_init] Azure v1 shim patch: ${step.name} needle not found, skipping.`);
    process.exit(0);
  }
}
for (const step of steps) {
  c = c.replace(step.needle, step.replacement);
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
const v017Needle = "          const req = clientMessage.request\n          currentRequestId = req.request_id || ''\n          sessionId = req.session_id || ''";
const replacement = "          const req = clientMessage.request\n          const requestedModel = String(req.model || '').trim()\n          const requestedProviderBaseUrl = String(req.provider_base_url || '').trim().replace(/\\/+$/, '')\n          const requestedProviderApiKey = String(req.provider_api_key || '').trim()\n          const requestedProviderApiFormat = String(req.provider_api_format || '').trim()\n          const previousOpenAIModel = process.env.OPENAI_MODEL\n          const previousOpenAIBaseUrl = process.env.OPENAI_BASE_URL\n          const previousOpenAIApiKey = process.env.OPENAI_API_KEY\n          const previousOpenAIApiFormat = process.env.OPENAI_API_FORMAT\n          if (requestedModel) {\n            // CappyCloud dynamic model override: OpenAI shim fallback paths read OPENAI_MODEL.\n            process.env.OPENAI_MODEL = requestedModel\n            console.log(`[grpc] dynamic model override: ${requestedModel}`)\n          }\n          if (requestedProviderBaseUrl && requestedProviderApiKey) {\n            // CappyCloud provider override: route this request to the selected provider without logging secrets.\n            process.env.OPENAI_BASE_URL = requestedProviderBaseUrl\n            process.env.OPENAI_API_KEY = requestedProviderApiKey\n            if (requestedProviderApiFormat === 'responses' || requestedProviderApiFormat === 'chat_completions') {\n              process.env.OPENAI_API_FORMAT = requestedProviderApiFormat\n            }\n            console.log(`[grpc] provider override: ${requestedProviderBaseUrl} format=${process.env.OPENAI_API_FORMAT || 'chat_completions'}`)\n          }\n          sessionId = req.session_id || ''";
const v017Replacement = "          const req = clientMessage.request\n          const requestedModel = String(req.model || '').trim()\n          const requestedProviderBaseUrl = String(req.provider_base_url || '').trim().replace(/\\/+$/, '')\n          const requestedProviderApiKey = String(req.provider_api_key || '').trim()\n          const requestedProviderApiFormat = String(req.provider_api_format || '').trim()\n          const previousOpenAIModel = process.env.OPENAI_MODEL\n          const previousOpenAIBaseUrl = process.env.OPENAI_BASE_URL\n          const previousOpenAIApiKey = process.env.OPENAI_API_KEY\n          const previousOpenAIApiFormat = process.env.OPENAI_API_FORMAT\n          if (requestedModel) {\n            // CappyCloud dynamic model override: OpenAI shim fallback paths read OPENAI_MODEL.\n            process.env.OPENAI_MODEL = requestedModel\n            console.log(`[grpc] dynamic model override: ${requestedModel}`)\n          }\n          if (requestedProviderBaseUrl && requestedProviderApiKey) {\n            // CappyCloud provider override: route this request to the selected provider without logging secrets.\n            process.env.OPENAI_BASE_URL = requestedProviderBaseUrl\n            process.env.OPENAI_API_KEY = requestedProviderApiKey\n            if (requestedProviderApiFormat === 'responses' || requestedProviderApiFormat === 'chat_completions') {\n              process.env.OPENAI_API_FORMAT = requestedProviderApiFormat\n            }\n            console.log(`[grpc] provider override: ${requestedProviderBaseUrl} format=${process.env.OPENAI_API_FORMAT || 'chat_completions'}`)\n          }\n          currentRequestId = req.request_id || ''\n          sessionId = req.session_id || ''";
if (c.includes(needle)) {
  c = c.replace(needle, replacement);
} else if (c.includes(v017Needle)) {
  c = c.replace(v017Needle, v017Replacement);
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
    # Provider "anthropic": depende do bloco de override inserido acima.
    node /patch_openclaude_anthropic_provider.js "$_GRPC_TS" || true
fi

# ── Exporta vars para openclaude e session_server ────────────
export CLAUDE_CODE_USE_OPENAI="${CLAUDE_CODE_USE_OPENAI}"
export OPENAI_BASE_URL="${OPENAI_BASE_URL}"
export OPENAI_API_KEY="${OPENAI_API_KEY}"
export OPENAI_MODEL="${OPENAI_MODEL}"
export GRPC_HOST="${GRPC_HOST}"
export GRPC_PORT="${GRPC_PORT}"
export DEVOPS_TOKEN="${DEVOPS_TOKEN:-}"
export GITHUB_TOKEN="${GITHUB_TOKEN:-}"

# ── Sobe o session server em background ──────────────────────
echo ""
echo "Starting session server on :${SESSION_SERVER_PORT}..."
SESSION_SERVER_PORT="${SESSION_SERVER_PORT}" node /session_server.js &
SESSION_SERVER_PID=$!
echo "Session server PID: ${SESSION_SERVER_PID}"

# ── Inicia o servidor gRPC do openclaude (processo principal) ─
if [ -f /tmp/cappycloud-openclaude-stopped ]; then
    echo "OpenClaude stopped by CappyCloud control plane; session server remains online."
    wait "${SESSION_SERVER_PID}"
fi

echo "Starting openclaude gRPC server on ${GRPC_HOST}:${GRPC_PORT}..."
cd /openclaude
exec npm run dev:grpc
