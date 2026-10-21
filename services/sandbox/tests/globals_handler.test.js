'use strict'
//   node --test services/sandbox/tests/globals_handler.test.js
const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('fs')
const os = require('os')
const path = require('path')

const { writeClaudeMd } = require('../globals_handler')

function setup(base = '# Regras base\n') {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'cappy-home-'))
  const basePath = path.join(home, 'base.md')
  fs.writeFileSync(basePath, base)
  const read = (dir) => fs.readFileSync(path.join(home, dir, 'CLAUDE.md'), 'utf8')
  return { home, basePath, read }
}

test('grava base + extras para o Claude CLI e para o openclaude', () => {
  const { home, basePath, read } = setup()
  writeClaudeMd(home, 'Use o banco de homologação.', basePath)
  const expected = '# Regras base\n\n## Instruções deste sandbox\n\nUse o banco de homologação.\n'
  assert.equal(read('.claude'), expected)
  assert.equal(read('.openclaude'), expected)
})

test('sem extras fica só a base (CLAUDE.md vazio no banco não apaga as regras)', () => {
  const { home, basePath, read } = setup()
  writeClaudeMd(home, 'algo', basePath)
  writeClaudeMd(home, '  \n', basePath)
  assert.equal(read('.claude'), '# Regras base\n')
})

test('na subida reaplica a base nova mantendo as extras salvas', () => {
  const { home, basePath, read } = setup()
  writeClaudeMd(home, 'Extra', basePath)
  fs.writeFileSync(basePath, '# Base v2\n')
  writeClaudeMd(home, undefined, basePath)
  assert.equal(read('.openclaude'), '# Base v2\n\n## Instruções deste sandbox\n\nExtra\n')
})

test('sem base e sem extras não deixa arquivo vazio', () => {
  const { home, basePath } = setup('')
  writeClaudeMd(home, '', basePath)
  assert.equal(fs.existsSync(path.join(home, '.claude', 'CLAUDE.md')), false)
})
