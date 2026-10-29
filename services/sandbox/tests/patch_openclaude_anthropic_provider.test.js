'use strict'
//   node --test services/sandbox/tests/patch_openclaude_anthropic_provider.test.js
const test = require('node:test')
const assert = require('node:assert/strict')
const vm = require('node:vm')

const { patchSource } = require('../patch_openclaude_anthropic_provider')

// Trecho com os mesmos needles que o env_init.sh deixa no server.ts do openclaude.
const SOURCE = [
  'async function handle(req, seen) {',
  '          const requestedModel = req.model',
  '          const requestedProviderBaseUrl = req.baseUrl',
  '          const requestedProviderApiKey = req.apiKey',
  '          const requestedProviderApiFormat = req.format',
  '          const previousOpenAIModel = undefined',
  '          if (requestedProviderBaseUrl && requestedProviderApiKey) {',
  "            console.log(`[grpc] provider override: ${requestedProviderBaseUrl} format=${process.env.OPENAI_API_FORMAT || 'chat_completions'}`)",
  '          }',
  '          seen.env = { ...process.env }',
  '          let engine = {}',
  '          engine = null',
  "          if (typeof previousOpenAIModel === 'string') {",
  '          }',
  '}',
  'module.exports = handle',
].join('\n')

function run(source, req, env) {
  const processStub = { env: { ...env } }
  const sandbox = { module: {}, console: { log() {} }, process: processStub, URL }
  vm.runInNewContext(source, sandbox)
  const seen = {}
  return sandbox.module.exports(req, seen).then(() => ({ during: seen.env, after: processStub.env }))
}

test('aplica uma vez e não duplica', () => {
  const first = patchSource(SOURCE)
  assert.equal(first.status, 'applied')
  assert.equal(patchSource(first.source).status, 'present')
})

test('sem o bloco de override o patch não mexe no arquivo', () => {
  const result = patchSource('const x = 1\n')
  assert.equal(result.status, 'missing-override')
  assert.equal(result.source, 'const x = 1\n')
})

test('Azure Foundry: desliga o shim OpenAI e restaura no fim', async () => {
  const { source } = patchSource(SOURCE)
  const env = { CLAUDE_CODE_USE_OPENAI: '1', OPENAI_BASE_URL: 'https://openrouter.ai/api/v1' }
  const { during, after } = await run(
    source,
    {
      model: 'claude-opus-5-5',
      baseUrl: 'https://recurso.services.ai.azure.com/anthropic',
      apiKey: 'chave',
      format: 'anthropic',
    },
    env,
  )

  assert.equal(during.CLAUDE_CODE_USE_OPENAI, undefined)
  assert.equal(during.CLAUDE_CODE_USE_FOUNDRY, '1')
  assert.equal(during.ANTHROPIC_FOUNDRY_BASE_URL, 'https://recurso.services.ai.azure.com/anthropic')
  assert.equal(during.ANTHROPIC_FOUNDRY_API_KEY, 'chave')
  assert.equal(during.ANTHROPIC_SMALL_FAST_MODEL, 'claude-opus-5-5')
  assert.equal(during.ANTHROPIC_DEFAULT_OPUS_MODEL, 'claude-opus-5-5')
  assert.match(during.ANTHROPIC_DEFAULT_OPUS_MODEL_SUPPORTED_CAPABILITIES, /adaptive_thinking/)
  assert.deepEqual(after, env)
})

test('Anthropic fora da Azure usa ANTHROPIC_BASE_URL', async () => {
  const { source } = patchSource(SOURCE)
  const { during } = await run(
    source,
    { model: 'claude-opus-4-1', baseUrl: 'https://api.anthropic.com', apiKey: 'chave', format: 'anthropic' },
    { CLAUDE_CODE_USE_OPENAI: '1' },
  )

  assert.equal(during.CLAUDE_CODE_USE_FOUNDRY, undefined)
  assert.equal(during.ANTHROPIC_BASE_URL, 'https://api.anthropic.com')
  assert.equal(during.ANTHROPIC_API_KEY, 'chave')
  // Claude 4.1 não tem adaptive thinking: não força a capability.
  assert.equal(during.ANTHROPIC_DEFAULT_OPUS_MODEL_SUPPORTED_CAPABILITIES, undefined)
})

test('outros formatos não mudam nada', async () => {
  const { source } = patchSource(SOURCE)
  const env = { CLAUDE_CODE_USE_OPENAI: '1' }
  const { during } = await run(
    source,
    { model: 'gpt-5.4', baseUrl: 'https://x.services.ai.azure.com/openai/v1', apiKey: 'k', format: 'responses' },
    env,
  )

  assert.equal(during.CLAUDE_CODE_USE_OPENAI, '1')
  assert.equal(during.CLAUDE_CODE_USE_FOUNDRY, undefined)
})
