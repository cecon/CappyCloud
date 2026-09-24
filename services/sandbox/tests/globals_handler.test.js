'use strict'
//   node --test services/sandbox/tests/globals_handler.test.js
const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('fs')
const os = require('os')
const path = require('path')

const { writeClaudeMd } = require('../globals_handler')

test('grava o CLAUDE.md do sandbox em ~/.claude', () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'cappy-home-'))
  writeClaudeMd(home, '# Regras')
  assert.equal(fs.readFileSync(path.join(home, '.claude', 'CLAUDE.md'), 'utf8'), '# Regras')
})

test('CLAUDE.md vazio apaga o arquivo para valer o padrão da imagem', () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'cappy-home-'))
  writeClaudeMd(home, '# Regras')
  writeClaudeMd(home, '  \n')
  assert.equal(fs.existsSync(path.join(home, '.claude', 'CLAUDE.md')), false)
  writeClaudeMd(home, '') // sem arquivo: não falha
})
