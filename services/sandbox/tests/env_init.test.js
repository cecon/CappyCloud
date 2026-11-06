'use strict'
//   node --test services/sandbox/tests/env_init.test.js
const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const source = fs.readFileSync(path.join(__dirname, '..', 'env_init.sh'), 'utf8')

test('shebang na primeira linha: o env_init.sh é o ENTRYPOINT do sandbox', () => {
  // Sem ele o container não sobe ("exec format error").
  assert.ok(source.startsWith('#!/usr/bin/env bash\n'))
})

test('patches do openclaude rodam depois do patch de modelo dinâmico', () => {
  const lines = source.split('\n')
  const anchor = lines.findIndex((line) => line.includes('/patch_openclaude_anthropic_provider.js'))
  assert.ok(anchor > 0)
  for (const script of ['/patch_openclaude_long_lines.js']) {
    const index = lines.findIndex((line) => line.includes(script))
    assert.ok(index > anchor, `${script} fora do bloco do gRPC`)
  }
})
