'use strict'
// Patch do gRPC do openclaude: provider no formato "anthropic".
//
// O override de provider do CappyCloud (env_init.sh) só troca a API estilo
// OpenAI. Claude no Azure Foundry recebe imagem só pela API de mensagens da
// Anthropic; pela rota estilo OpenAI a Azure aceita a chamada e descarta a
// imagem. Com ``provider_api_format = "anthropic"`` este patch desliga o shim
// OpenAI naquela requisição e usa o cliente Anthropic do openclaude (Foundry
// para hosts ``*.services.ai.azure.com``), restaurando as variáveis no fim.
//
// O openclaude desliga o prompt cache fora da API oficial, mas a API de mensagens
// do Foundry aceita ``cache_control``: sem ele as chamadas saem ~2,8x mais caras.
// Por isso o patch também liga o cache, só nas requisições desse provider.
//
// Roda em tempo de execução, depois do patch de modelo dinâmico do env_init.sh,
// porque depende do bloco "CappyCloud provider override" que ele insere.
//   node /patch_openclaude_anthropic_provider.js /openclaude/src/grpc/server.ts

const fs = require('fs')
const path = require('path')

const MARKER = 'CappyCloud anthropic provider'

const OVERRIDE_NEEDLE =
  "            console.log(`[grpc] provider override: ${requestedProviderBaseUrl} format=${process.env.OPENAI_API_FORMAT || 'chat_completions'}`)\n" +
  '          }\n'

// Modelos auxiliares (título, resumo) e tiers apontam para o modelo pedido: o
// recurso da Azure só tem os deployments cadastrados. Claude 4.6+ exige
// "adaptive thinking", que o openclaude só reconhece pelo nome até a 4.8.
const OVERRIDE_BLOCK = [
  `          // ${MARKER}: Claude pela API de mensagens (Azure Foundry ou Anthropic).`,
  "          const cappycloudModelTiers = ['ANTHROPIC_DEFAULT_OPUS_MODEL', 'ANTHROPIC_DEFAULT_SONNET_MODEL', 'ANTHROPIC_DEFAULT_HAIKU_MODEL']",
  "          const cappycloudAnthropicKeys = ['CLAUDE_CODE_USE_OPENAI', 'CLAUDE_CODE_USE_FOUNDRY', 'ANTHROPIC_FOUNDRY_BASE_URL', 'ANTHROPIC_FOUNDRY_API_KEY', 'ANTHROPIC_BASE_URL', 'ANTHROPIC_API_KEY', 'CAPPYCLOUD_ANTHROPIC_PROMPT_CACHE', 'ANTHROPIC_MODEL', 'ANTHROPIC_SMALL_FAST_MODEL', ...cappycloudModelTiers, ...cappycloudModelTiers.map(tier => `${tier}_SUPPORTED_CAPABILITIES`)]",
  '          const previousAnthropicEnv = Object.fromEntries(cappycloudAnthropicKeys.map(key => [key, process.env[key]]))',
  "          if (requestedProviderApiFormat === 'anthropic' && requestedProviderBaseUrl && requestedProviderApiKey) {",
  '            delete process.env.CLAUDE_CODE_USE_OPENAI',
  "            process.env.CAPPYCLOUD_ANTHROPIC_PROMPT_CACHE = '1'",
  '            if (requestedModel) {',
  '              process.env.ANTHROPIC_MODEL = requestedModel',
  '              process.env.ANTHROPIC_SMALL_FAST_MODEL = requestedModel',
  '              const cappycloudVersion = /claude-(?:opus|sonnet|haiku)-(\\d+)-(\\d+)/i.exec(requestedModel)',
  '              const cappycloudAdaptive = !!cappycloudVersion && (Number(cappycloudVersion[1]) > 4 || (Number(cappycloudVersion[1]) === 4 && Number(cappycloudVersion[2]) >= 6))',
  '              for (const tier of cappycloudModelTiers) {',
  '                process.env[tier] = requestedModel',
  "                if (cappycloudAdaptive) process.env[`${tier}_SUPPORTED_CAPABILITIES`] = 'effort,thinking,adaptive_thinking,interleaved_thinking'",
  '              }',
  '            }',
  "            let cappycloudAnthropicHost = ''",
  '            try {',
  '              cappycloudAnthropicHost = new URL(requestedProviderBaseUrl).hostname.toLowerCase()',
  '            } catch {}',
  "            if (cappycloudAnthropicHost.endsWith('.services.ai.azure.com')) {",
  "              process.env.CLAUDE_CODE_USE_FOUNDRY = '1'",
  '              process.env.ANTHROPIC_FOUNDRY_BASE_URL = requestedProviderBaseUrl',
  '              process.env.ANTHROPIC_FOUNDRY_API_KEY = requestedProviderApiKey',
  '            } else {',
  '              process.env.ANTHROPIC_BASE_URL = requestedProviderBaseUrl',
  '              process.env.ANTHROPIC_API_KEY = requestedProviderApiKey',
  '            }',
  '            console.log(`[grpc] anthropic provider: ${requestedProviderBaseUrl}`)',
  '          }',
  '',
].join('\n')

const RESET_NEEDLE =
  "          engine = null\n          if (typeof previousOpenAIModel === 'string') {"

const RESET_BLOCK = [
  '          engine = null',
  '          for (const [key, value] of Object.entries(previousAnthropicEnv)) {',
  "            if (typeof value === 'string') {",
  '              process.env[key] = value',
  '            } else {',
  '              delete process.env[key]',
  '            }',
  '          }',
  "          if (typeof previousOpenAIModel === 'string') {",
].join('\n')

const CACHE_MARKER = 'CappyCloud anthropic prompt cache'

const CACHE_NEEDLE = 'export function getPromptCachingEnabled(model: string): boolean {\n'

const CACHE_BLOCK = [
  `  // ${CACHE_MARKER}: a API de mensagens do Foundry aceita cache_control.`,
  "  if (process.env.CAPPYCLOUD_ANTHROPIC_PROMPT_CACHE === '1') {",
  '    return !isEnvTruthy(process.env.DISABLE_PROMPT_CACHING)',
  '  }',
  '',
].join('\n')

/** Liga o cache em ``services/api/claude.ts``; mesmo retorno de ``patchSource``. */
function patchCacheSource(source) {
  if (source.includes(CACHE_MARKER)) return { source, status: 'present' }
  if (!source.includes(CACHE_NEEDLE)) return { source, status: 'missing-cache-function' }
  return { source: source.replace(CACHE_NEEDLE, CACHE_NEEDLE + CACHE_BLOCK), status: 'applied' }
}

/** Devolve ``{ source, status }``; ``status`` é applied, present ou o needle que faltou. */
function patchSource(source) {
  if (source.includes(MARKER)) return { source, status: 'present' }
  if (!source.includes(OVERRIDE_NEEDLE)) return { source, status: 'missing-override' }
  if (!source.includes(RESET_NEEDLE)) return { source, status: 'missing-reset' }
  const patched = source
    .replace(OVERRIDE_NEEDLE, OVERRIDE_NEEDLE + OVERRIDE_BLOCK)
    .replace(RESET_NEEDLE, RESET_BLOCK)
  return { source: patched, status: 'applied' }
}

function applyPatch(file, patch, label) {
  const { source, status } = patch(fs.readFileSync(file, 'utf8'))
  if (status === 'applied') fs.writeFileSync(file, source)
  console.log(`[env_init] ${label} patch: ${status}.`)
}

function main(grpcServerFile) {
  applyPatch(grpcServerFile, patchSource, 'gRPC anthropic provider')
  const claudeFile = path.join(path.dirname(grpcServerFile), '..', 'services', 'api', 'claude.ts')
  applyPatch(claudeFile, patchCacheSource, 'anthropic prompt cache')
}

if (require.main === module) main(process.argv[2])

module.exports = { patchSource, patchCacheSource, MARKER }
