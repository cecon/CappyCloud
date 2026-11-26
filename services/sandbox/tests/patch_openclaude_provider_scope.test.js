'use strict'
//   node --test services/sandbox/tests/patch_openclaude_provider_scope.test.js
const test = require('node:test')
const assert = require('node:assert/strict')

const { MARKER, patchServerSource } = require('../patch_openclaude_provider_scope')

// Trecho com os mesmos needles do server.ts do openclaude (handleChat).
const SERVER = [
  "import * as grpc from '@grpc/grpc-js'",
  "import fs from 'fs'",
  'class GrpcServer {',
  '  private handleChat(call) {',
  "    call.on('data', async (clientMessage) => {",
  '      try {',
  '        process.env.OPENAI_API_KEY = clientMessage.key',
  '      } catch (err) {',
  '        call.end()',
  '      }',
  '    })',
  '',
  "    call.on('end', () => {",
  '      interrupted = true',
  '    })',
  '  }',
  '}',
].join('\n')

test('aplica uma vez: import do escopo, abertura e fechamento do wrap', () => {
  const first = patchServerSource(SERVER)
  assert.equal(first.status, 'applied')
  assert.ok(first.source.includes(MARKER))
  assert.ok(first.source.includes("import { AsyncLocalStorage as CappyProviderStorage } from 'node:async_hooks'"))
  assert.ok(first.source.includes("call.on('data', (clientMessage) => cappyProviderStore.run(cappyProviderScope, async () => {"))
  assert.ok(first.source.includes("        call.end()\n      }\n    }))\n\n    call.on('end', () => {"))
  // O import do grpc continua sendo a primeira linha.
  assert.ok(first.source.startsWith("import * as grpc from '@grpc/grpc-js'\n"))
  assert.equal(patchServerSource(first.source).status, 'present')
})

test('abertura e fechamento ficam balanceados', () => {
  const { source } = patchServerSource(SERVER)
  const opens = (source.match(/cappyProviderStore\.run\(/g) || []).length
  assert.equal(opens, 1)
  assert.equal((source.match(/\(/g) || []).length, (source.match(/\)/g) || []).length)
})

test('sem algum trecho, não mexe no arquivo', () => {
  const semFechamento = SERVER.replace("    call.on('end', () => {", "    call.on('close', () => {")
  assert.deepEqual(patchServerSource(semFechamento), { source: semFechamento, status: 'missing-fechamento' })
  const semImport = SERVER.replace("import * as grpc from '@grpc/grpc-js'\n", '')
  assert.equal(patchServerSource(semImport).status, 'missing-import')
})

test('trecho repetido conta como ausente (o wrap fecharia no lugar errado)', () => {
  const duplicado = `${SERVER}\n${SERVER.split('\n').slice(4, 11).join('\n')}\n`
  assert.equal(patchServerSource(duplicado).status, 'missing-abertura')
})
