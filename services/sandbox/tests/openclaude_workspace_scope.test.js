'use strict'
// node --test services/sandbox/tests/openclaude_workspace_scope.test.js
// Monta um server.ts com o guard real do multimodal-grpc-handler.patch, aplica
// o patch_openclaude_grpc_v024.js e testa o guard resultante (node remove os tipos).
const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('fs')
const os = require('os')
const path = require('path')
const { pathToFileURL } = require('url')

const { patchServer } = require('../patch_openclaude_grpc_v024')

const SANDBOX = path.join(__dirname, '..')
const GUARD_NAMES = [
  'CAPPYCLOUD_PATH_GUARDED_TOOLS',
  'CAPPYCLOUD_COMMAND_GUARDED_TOOLS',
  'CAPPYCLOUD_PATH_INPUT_KEYS',
  'cappycloudIsInsideWorktree',
  'cappycloudResolveToolPath',
  'cappycloudCollectPathInputs',
  'cappycloudExtractRepoPaths',
  'cappycloudValidateToolScope',
]

/** Recorta do patch os blocos adicionados (const/function) do guard original. */
function strictGuardFromPatch() {
  const added = fs
    .readFileSync(path.join(SANDBOX, 'patches', 'multimodal-grpc-handler.patch'), 'utf8')
    .split('\n')
    .filter((line) => line.startsWith('+') && !line.startsWith('+++'))
    .map((line) => line.slice(1))
  const blocks = []
  for (const name of GUARD_NAMES) {
    const start = added.findIndex((line) => new RegExp(`^(const|function) ${name}\\b`).test(line))
    assert.notEqual(start, -1, `${name} não está no patch`)
    let end = start
    // Bloco termina na linha que fecha em col 0 (`}`, `])`, `]`) ou na própria linha se for const de uma linha.
    while (!/^[}\]]/.test(added[end]) && !/^const .*[)\]]$/.test(added[end])) end += 1
    blocks.push(added.slice(start, end + 1).join('\n'))
  }
  return blocks.join('\n\n')
}

async function loadGuard() {
  // posix: no container o path é Linux (o teste também roda no Windows).
  const fakeServer = `import { posix as path } from 'node:path'\nconst MAX_SESSIONS = 1000\n\n${strictGuardFromPatch()}\n`
  const patched = patchServer(
    fakeServer,
    '',
    fs.readFileSync(path.join(SANDBOX, 'cappycloud_grpc_workspace_scope_v024.ts'), 'utf8'),
    fs.readFileSync(path.join(SANDBOX, 'readonly_commands.js'), 'utf8'),
  )
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'oc-scope-'))
  const file = path.join(dir, 'server.ts')
  fs.writeFileSync(file, `${patched}\nexport { cappycloudValidateToolScope }\n`)
  return (await import(pathToFileURL(file).href)).cappycloudValidateToolScope
}

const SESSION = '/repos/workspaces/proteus/sessions/f57c1f57dc7c'
const REPO = '/repos/workspaces/proteus/repos/PROTEUS'

test('lê repos e conhecimento do workspace com Read/Grep/Glob', async () => {
  const guard = await loadGuard()
  assert.equal(guard('Read', { file_path: `${REPO}/README.md` }, SESSION), null)
  assert.equal(guard('Grep', { pattern: 'NFSE', path: `${REPO}/TSS` }, SESSION), null)
  assert.equal(guard('Glob', { pattern: '**/*.prw', path: '/repos/workspaces/proteus/knowledge' }, SESSION), null)
  assert.equal(guard('Read', { file_path: '/repos/workspaces/proteus/CLAUDE.md' }, SESSION), null)
})

test('Bash de leitura passa nos repos do workspace', async () => {
  const guard = await loadGuard()
  assert.equal(guard('Bash', { command: `ls -la ${REPO}` }, SESSION), null)
  assert.equal(guard('Bash', { command: `rg -n "tomador" ${REPO}/TSS | head -20` }, SESSION), null)
  assert.equal(guard('Bash', { command: `cd ${REPO} && git log --oneline -5` }, SESSION), null)
})

test('escrita e saída do workspace continuam bloqueadas', async () => {
  const guard = await loadGuard()
  assert.match(guard('Write', { file_path: `${REPO}/x.txt`, content: 'x' }, SESSION), /Tool blocked/)
  assert.match(guard('Edit', { file_path: `${REPO}/README.md` }, SESSION), /Tool blocked/)
  assert.match(guard('Bash', { command: `rm -rf ${REPO}/TSS` }, SESSION), /Tool blocked/)
  assert.match(guard('Bash', { command: `echo x > ${REPO}/a.txt` }, SESSION), /Tool blocked/)
  assert.match(guard('Read', { file_path: '/repos/workspaces/outro/repos/X/a.md' }, SESSION), /Tool blocked/)
  assert.match(guard('Read', { file_path: '/etc/passwd' }, SESSION), /Tool blocked/)
})

test('sessão fora de workspace mantém o guard estrito', async () => {
  const guard = await loadGuard()
  const worktree = '/repos/sessions/abc123'
  assert.match(guard('Read', { file_path: '/repos/PROTEUS/README.md' }, worktree), /Tool blocked/)
  assert.equal(guard('Read', { file_path: `${worktree}/a.md` }, worktree), null)
})

test('aplicar o patch duas vezes não duplica o bloco', async () => {
  const scope = fs.readFileSync(path.join(SANDBOX, 'cappycloud_grpc_workspace_scope_v024.ts'), 'utf8')
  const readonly = fs.readFileSync(path.join(SANDBOX, 'readonly_commands.js'), 'utf8')
  const base = `import path from 'path'\nconst MAX_SESSIONS = 1000\n\n${strictGuardFromPatch()}\n`
  const once = patchServer(base, '', scope, readonly)
  assert.equal(patchServer(once, '', scope, readonly), once)
})
