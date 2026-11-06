'use strict'
//   node --test services/sandbox/tests/patch_openclaude_cache_usage.test.js
const test = require('node:test')
const assert = require('node:assert/strict')
const vm = require('node:vm')

const { patchServerSource, patchProtoSource } = require('../patch_openclaude_cache_usage')

// Trecho com os mesmos needles do server.ts do openclaude (commit 88baafe).
const SERVER = [
  'function handle(usage, call) {',
  '          let promptTokens = 0',
  '          let completionTokens = 0',
  '                const freshInputTokens = usage.input_tokens ?? 0',
  '                const cacheReadTokens = usage.cache_read_input_tokens ?? 0',
  '                const cacheCreationTokens = usage.cache_creation_input_tokens ?? 0',
  '                promptTokens = freshInputTokens + cacheReadTokens + cacheCreationTokens',
  '                completionTokens = usage.output_tokens ?? 0',
  '            call.write({',
  '              done: {',
  '                prompt_tokens: promptTokens,',
  '                completion_tokens: completionTokens',
  '              }',
  '            })',
  '}',
  'module.exports = handle',
].join('\n')

const PROTO = [
  'message FinalResponse {',
  '  string full_text = 1; // fallback when provider returns only final result',
  '  uint32 prompt_tokens     = 2;',
  '  uint32 completion_tokens = 3;',
  '}',
].join('\n')

test('server: aplica uma vez e manda as parcelas de cache no done', () => {
  const first = patchServerSource(SERVER)
  assert.equal(first.status, 'applied')
  assert.equal(patchServerSource(first.source).status, 'present')

  const sandbox = { module: {} }
  vm.runInNewContext(first.source, sandbox)
  const written = []
  sandbox.module.exports(
    { input_tokens: 1000, cache_read_input_tokens: 30000, cache_creation_input_tokens: 2000, output_tokens: 500 },
    { write: (msg) => written.push(msg) },
  )
  assert.deepEqual({ ...written[0].done }, {
    prompt_tokens: 33000,
    completion_tokens: 500,
    cache_read_tokens: 30000,
    cache_write_tokens: 2000,
  })
})

test('server: sem um dos needles não mexe no arquivo', () => {
  const result = patchServerSource(SERVER.replace('let completionTokens = 0', 'let x = 0'))
  assert.equal(result.status, 'missing-declaração')
  assert.equal(patchServerSource('const x = 1').source, 'const x = 1')
})

test('proto: ganha os campos 4 e 5, iguais aos do CappyCloud', () => {
  const first = patchProtoSource(PROTO)
  assert.equal(first.status, 'applied')
  assert.match(first.source, /uint32 cache_read_tokens {2}= 4;/)
  assert.match(first.source, /uint32 cache_write_tokens = 5;/)
  assert.equal(patchProtoSource(first.source).status, 'present')
  assert.equal(patchProtoSource('message X {}').status, 'missing-final-response')
})
