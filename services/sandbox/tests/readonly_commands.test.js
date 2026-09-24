'use strict'
// node --test services/sandbox/tests/readonly_commands.test.js
const test = require('node:test')
const assert = require('node:assert/strict')

const { isReadOnlyCommand } = require('../readonly_commands')
const { validateToolScope } = require('../claude_runtime_mapper')

const SESSION = '/repos/workspaces/smartpos/sessions/2d6808e44eac'
const RO = '/repos/workspaces/smartpos/repos/smartpos'

test('comandos de leitura passam', () => {
  for (const cmd of [
    `grep -n "watermelon" ${RO}/package.json -i`,
    `find ${RO}/src -iname "*schema*" 2>/dev/null`,
    `rg -n "schemaVersion" ${RO}/src | head -20`,
    `sed -n '1,80p' ${RO}/src/db/index.js`,
    `cd ${RO} && git log --oneline -5`,
    `find ${RO} -name "*.js" | xargs grep -l Realm`,
    `cat ${RO}/package.json | jq .dependencies`,
  ]) {
    assert.equal(isReadOnlyCommand(cmd), true, cmd)
  }
})

test('escrita, edição, remoção e execução continuam bloqueadas', () => {
  for (const cmd of [
    `echo x > ${RO}/TESTE.md`,
    `cat a >> ${RO}/b`,
    `sed -i 's/a/b/' ${RO}/x.js`,
    `find ${RO} -name "*.log" -delete`,
    `find ${RO} -exec rm {} \;`,
    `rm -rf ${RO}/src`,
    `cd ${RO} && git checkout -- .`,
    `tee ${RO}/x < /dev/null`,
    `cat $(rm -rf ${RO}/x)`,
    `ls ${RO} &> ${RO}/saida.txt`,
    `(cd ${RO} && touch novo)`,
    `find ${RO} | xargs rm`,
    `awk 'BEGIN{system("rm x")}' ${RO}/a`,
  ]) {
    assert.equal(isReadOnlyCommand(cmd), false, cmd)
  }
})

test('guard: Bash de leitura no repo somente leitura passa; escrita é bloqueada com dica', () => {
  const ok = validateToolScope('Bash', { command: `grep -rn "version" ${RO}/src` }, SESSION)
  assert.equal(ok, null)
  const blocked = validateToolScope('Bash', { command: `echo x > ${RO}/TESTE.md` }, SESSION)
  assert.match(blocked, /Somente leitura/)
  // Fora do workspace continua bloqueado mesmo sendo leitura.
  assert.match(validateToolScope('Bash', { command: 'cat /repos/Seller/x' }, SESSION), /outside the conversation worktree/)
  // Sessão legada (sem workspace) não ganha nada.
  assert.match(validateToolScope('Bash', { command: `cat ${RO}/x` }, '/repos/sessions/abc/Seller'), /outside/)
})

test('sed -n lê, sed -i edita', () => {
  assert.equal(isReadOnlyCommand(`sed -n '1,5p' ${RO}/a`), true)
  assert.equal(isReadOnlyCommand(`sed -ni 's/a/b/p' ${RO}/a`), false)
  assert.equal(isReadOnlyCommand(`sed -i.bak 's/a/b/' ${RO}/a`), false)
  assert.equal(isReadOnlyCommand(`grep -i foo ${RO}/a`), true)
})

test('comandos reais dos subagentes: aspas com | e $(...) só de leitura', () => {
  for (const cmd of [
    `grep -nE '"(name|version)"' ${RO}/package.json`,
    `cd ${RO} && echo "total: $(find . -type f -name '*.js' | wc -l)"; ls -d node_modules .git 2>&1`,
    `grep '<View>' ${RO}/src/App.js`,
    `wc -l < ${RO}/package.json`,
    `ls ${RO} &>/dev/null`,
    `(cd ${RO} && ls)`,
  ]) {
    assert.equal(isReadOnlyCommand(cmd), true, cmd)
  }
})

test('graphify só com os subcomandos de consulta', () => {
  const graph = '/repos/workspaces/loja/knowledge/graphify/graph.json'
  assert.equal(isReadOnlyCommand(`graphify query "fluxo de venda" --graph ${graph} --budget 1500`), true)
  assert.equal(isReadOnlyCommand(`graphify explain "SaleService" --graph ${graph}`), true)
  assert.equal(isReadOnlyCommand('graphify update /repos/workspaces/loja/repos/pdv'), false)
  assert.equal(isReadOnlyCommand(`graphify merge-graphs a.json b.json --out ${graph}`), false)
})
