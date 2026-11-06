'use strict'
//   node --test services/sandbox/tests/patch_openclaude_long_lines.test.js
const test = require('node:test')
const assert = require('node:assert/strict')
const vm = require('node:vm')

const { patchSource, MAX_LINE_CHARS } = require('../patch_openclaude_long_lines')

// Trecho com os mesmos needles do FileReadTool.ts do openclaude (commit 88baafe).
const SOURCE = [
  'async function readText(content, ext, maxTokens, file_path, totalLines, lineOffset, seen) {',
  '  await validateContentTokens(content, ext, maxTokens, {',
  '    filePath: file_path,',
  '    totalLines,',
  '  })',
  '  seen.state = content',
  '  const data = {',
  "    type: 'text' as const,",
  '    file: {',
  '      filePath: file_path,',
  '      content,',
  '    },',
  '  }',
  '  return data',
  '}',
].join('\n')

function run(patched, content, lineOffset = 0) {
  const js = patched.replace(" as const", '') + '\nmodule.exports = readText'
  const sandbox = { module: {}, validated: [] }
  vm.runInNewContext(
    `async function validateContentTokens(c) { validated.push(c) }\n${js}`,
    sandbox,
  )
  const seen = {}
  return sandbox.module
    .exports(content, 'json', 25000, '/repos/w/New Nfse/tssnewnfse.json', 10, lineOffset, seen)
    .then((data) => ({ data, seen, validated: sandbox.validated }))
}

test('aplica uma vez e não duplica', () => {
  const first = patchSource(SOURCE)
  assert.equal(first.status, 'applied')
  assert.equal(patchSource(first.source).status, 'present')
})

test('sem os needles o patch não mexe no arquivo', () => {
  const result = patchSource('const x = 1\n')
  assert.equal(result.status, 'missing-validate')
  assert.equal(result.source, 'const x = 1\n')
})

test('corta a linha gigante e ensina a decodificar pelo Bash', async () => {
  const { source } = patchSource(SOURCE)
  const giant = '  "xml_depara": "' + 'A'.repeat(100000) + '",'
  const content = ['  {', giant, '  "cod_mun": "3548500",'].join('\n')

  const { data, seen, validated } = await run(source, content, 10348)

  const shown = data.file.content.split('\n')
  assert.equal(shown[0], '  {')
  assert.ok(shown[1].length < 2600)
  assert.ok(shown[1].startsWith(giant.slice(0, MAX_LINE_CHARS)))
  assert.match(shown[1], /linha 10350 tem 100019 caracteres/)
  assert.match(shown[1], /sed -n '10350p' "\/repos\/w\/New Nfse\/tssnewnfse.json" \| sed -E/)
  assert.match(shown[1], /base64 -d\]$/)
  assert.equal(shown[2], '  "cod_mun": "3548500",')
  // O limite de tokens olha o que vai para o modelo; o estado guarda o original.
  assert.equal(validated[0], data.file.content)
  assert.equal(seen.state, content)
})

test('arquivo com linhas normais passa igual', async () => {
  const { source } = patchSource(SOURCE)
  const content = 'linha 1\nlinha 2'
  const { data } = await run(source, content)
  assert.equal(data.file.content, content)
})
