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
// Roda em tempo de execução, depois do patch de modelo dinâmico do env_init.sh,
// porque depende do bloco "CappyCloud provider override" que ele insere.
//   node /patch_openclaude_anthropic_provider.js /openclaude/src/grpc/server.ts

const fs = require('fs')

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
  "          const cappycloudAnthropicKeys = ['CLAUDE_CODE_USE_OPENAI', 'CLAUDE_CODE_USE_FOUNDRY', 'ANTHROPIC_FOUNDRY_BASE_URL', 'ANTHROPIC_FOUNDRY_API_KEY', 'ANTHROPIC_BASE_URL', 'ANTHROPIC_API_KEY', 'ANTHROPIC_MODEL', 'ANTHROPIC_SMALL_FAST_MODEL', ...cappycloudModelTiers, ...cappycloudModelTiers.map(tier => `${tier}_SUPPORTED_CAPABILITIES`)]",
  '          const previousAnthropicEnv = Object.fromEntries(cappycloudAnthropicKeys.map(key => [key, process.env[key]]))',
  "          if (requestedProviderApiFormat === 'anthropic' && requestedProviderBaseUrl && requestedProviderApiKey) {",
  '            delete process.env.CLAUDE_CODE_USE_OPENAI',
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

function main(file) {
  const { source, status } = patchSource(fs.readFileSync(file, 'utf8'))
  if (status === 'applied') fs.writeFileSync(file, source)
  console.log(`[env_init] gRPC anthropic provider patch: ${status}.`)
}

if (require.main === module) main(process.argv[2])

module.exports = { patchSource, MARKER }
