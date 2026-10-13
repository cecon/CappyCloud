'use strict'
//   node --test services/sandbox/tests/claude_runtime_env.test.js
const test = require('node:test')
const assert = require('node:assert/strict')

const { sdkEnv } = require('../claude_runtime_setup')

test('janela de compactação padrão de 150 mil tokens, sobrescrita pelo ambiente', () => {
  const saved = process.env.CLAUDE_CODE_AUTO_COMPACT_WINDOW
  try {
    delete process.env.CLAUDE_CODE_AUTO_COMPACT_WINDOW
    assert.equal(sdkEnv().CLAUDE_CODE_AUTO_COMPACT_WINDOW, '150000')
    process.env.CLAUDE_CODE_AUTO_COMPACT_WINDOW = '80k'
    assert.equal(sdkEnv().CLAUDE_CODE_AUTO_COMPACT_WINDOW, '80k')
  } finally {
    if (saved === undefined) delete process.env.CLAUDE_CODE_AUTO_COMPACT_WINDOW
    else process.env.CLAUDE_CODE_AUTO_COMPACT_WINDOW = saved
  }
})
