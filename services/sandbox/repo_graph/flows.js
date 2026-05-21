'use strict'

const { readBalancedExpression, splitTopLevelArgs } = require('./text')

function cleanSqlTableName(value) {
  return value
    .replace(/["'`()[\];]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 90)
}

function extractPythonFlowTargets(raw) {
  const calls = new Set()
  const queries = new Set()
  const persists = new Set()
  const ignoredCalls = new Set([
    'False',
    'None',
    'True',
    'abs',
    'append',
    'bool',
    'connect',
    'copy',
    'dict',
    'enumerate',
    'exists',
    'float',
    'format',
    'get',
    'getattr',
    'hasattr',
    'int',
    'len',
    'list',
    'max',
    'min',
    'not',
    'open',
    'print',
    'range',
    'set',
    'setattr',
    'sorted',
    'str',
    'startswith',
    'startfile',
    'sum',
    'super',
    'tuple',
  ])

  for (const match of raw.matchAll(/\b(?:self\.|cls\.|[A-Za-z_]\w+\.)?([A-Za-z_]\w*)\s*\(/g)) {
    const name = match[1]
    if (!name || ignoredCalls.has(name) || name.startsWith('__')) continue
    calls.add(name)
  }

  for (const match of raw.matchAll(/\b(?:from|join)\s+([A-Za-z_][\w.]*)/gi)) {
    const table = cleanSqlTableName(match[1])
    if (table && !['select', 'where'].includes(table.toLowerCase())) queries.add(table)
  }
  for (const match of raw.matchAll(/\b(?:insert\s+into|update|delete\s+from)\s+([A-Za-z_][\w.]*)/gi)) {
    const table = cleanSqlTableName(match[1])
    if (table) persists.add(table)
  }

  return {
    routes: [],
    actions: [],
    calls: Array.from(calls).sort(),
    queries: Array.from(queries).sort(),
    persists: Array.from(persists).sort(),
  }
}

function extractFlowTargets(raw) {
  const routes = new Set()
  const calls = new Set()
  const actions = new Set()
  const ignoredCalls = new Set([
    'Boolean',
    'Date',
    'Error',
    'Number',
    'Object',
    'Promise',
    'String',
    'alert',
    'call',
    'console',
    'dispatch',
    'filter',
    'find',
    'if',
    'map',
    'navigate',
    'notification',
    'parseFloat',
    'parseInt',
    'put',
    'reduce',
    'replace',
    'render',
    'setState',
    'slice',
    'sort',
  ])

  for (const match of raw.matchAll(/\b(?:NavigationService\.)?(?:navigation\.)?navigate\s*\(\s*['"]([^'"]+)['"]/g)) {
    routes.add(match[1])
  }
  for (const match of raw.matchAll(/\b(?:routeName|screen)\s*:\s*['"]([^'"]+)['"]/g)) {
    routes.add(match[1])
  }
  for (const match of raw.matchAll(/\b[A-Za-z_$][\w$]*(?:Navigate|Navigation)[A-Za-z_$\w]*\s*\(\s*['"]([^'"]+)['"]/gi)) {
    routes.add(match[1])
  }
  for (const match of raw.matchAll(/\b(?:dispatch|put)\s*\(\s*([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)?)/g)) {
    actions.add(match[1])
  }
  for (const match of raw.matchAll(/\b(?:this\.|props\.|ctrl\.)?([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)?)\s*\(/g)) {
    const name = match[1].split('.').pop()
    if (!name || ignoredCalls.has(name) || /^[A-Z][A-Z0-9_]+$/.test(name)) continue
    calls.add(name)
  }

  return {
    routes: Array.from(routes).sort(),
    calls: Array.from(calls).sort(),
    actions: Array.from(actions).sort(),
  }
}

function cleanSagaExpression(raw) {
  return raw
    .trim()
    .replace(/^yield\s+/, '')
    .replace(/^return\s+/, '')
    .replace(/^\*\s*/, '')
    .replace(/;$/, '')
    .trim()
}

function sagaActionNamesFromArg(raw) {
  const value = cleanSagaExpression(raw)
  if (!value) return []

  if (value.startsWith('[') && value.endsWith(']')) {
    return splitTopLevelArgs(value.slice(1, -1)).flatMap(sagaActionNamesFromArg)
  }

  const objectType = value.match(/\btype\s*:\s*([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)/)
  if (objectType) return [objectType[1]]

  const stringLiteral = value.match(/^['"`]([^'"`]+)['"`]$/)
  if (stringLiteral) return [stringLiteral[1]]

  const actionCreator = value.match(/^([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*\(/)
  if (actionCreator) return [actionCreator[1]]

  const typeMember = value.match(/^([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)/)
  if (typeMember) return [typeMember[1].replace(/\.type$/, '')]

  return []
}

function sagaCallableName(raw) {
  const value = cleanSagaExpression(raw)
  const member = value.match(/^([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)/)
  if (!member) return ''
  return member[1].split('.').pop() || ''
}

function readCallArguments(raw, callMatch) {
  const parenStart = raw.indexOf('(', (callMatch.index || 0) + callMatch[0].length - 1)
  if (parenStart < 0) return []
  return splitTopLevelArgs(readBalancedExpression(raw, parenStart, '(', ')'))
}

function extractSagaEffects(raw) {
  const watchers = []
  const puts = []
  const calls = []
  const selects = []
  const forks = []

  for (const match of raw.matchAll(/\b(takeLatest|takeEvery|takeLeading|takeMaybe|throttle|debounce)\s*\(/g)) {
    const args = readCallArguments(raw, match)
    const actionIndex = ['throttle', 'debounce'].includes(match[1]) ? 1 : 0
    const workerIndex = ['throttle', 'debounce'].includes(match[1]) ? 2 : 1
    const worker = sagaCallableName(args[workerIndex] || '')
    for (const action of sagaActionNamesFromArg(args[actionIndex] || '')) {
      watchers.push({ effect: match[1], action, worker })
    }
  }

  for (const match of raw.matchAll(/\bput\s*\(/g)) {
    const args = readCallArguments(raw, match)
    sagaActionNamesFromArg(args[0] || '').forEach((action) => puts.push(action))
  }

  for (const match of raw.matchAll(/\bcall\s*\(/g)) {
    const args = readCallArguments(raw, match)
    const name = sagaCallableName(args[0] || '')
    if (name) calls.push(name)
  }

  for (const match of raw.matchAll(/\bselect\s*\(/g)) {
    const args = readCallArguments(raw, match)
    const name = sagaCallableName(args[0] || '')
    if (name) selects.push(name)
  }

  for (const match of raw.matchAll(/\bfork\s*\(/g)) {
    const args = readCallArguments(raw, match)
    const name = sagaCallableName(args[0] || '')
    if (name) forks.push(name)
  }

  return {
    watchers,
    puts: Array.from(new Set(puts)).sort(),
    calls: Array.from(new Set(calls)).sort(),
    selects: Array.from(new Set(selects)).sort(),
    forks: Array.from(new Set(forks)).sort(),
  }
}

function looksLikeSagaFile(file, content) {
  return (
    /sagas?\//i.test(file) ||
    /sagas?\.(?:js|jsx|ts|tsx)$/i.test(file) ||
    /redux-saga\/effects/.test(content) ||
    /\b(takeLatest|takeEvery|takeLeading|put|call|select|fork)\s*\(/.test(content)
  )
}

function looksLikeReducerFile(file, content) {
  return (
    /reducers?\//i.test(file) ||
    /reducers?\.(?:js|jsx|ts|tsx)$/i.test(file) ||
    /\bswitch\s*\([^)]*action\.type[^)]*\)/.test(content) ||
    /\b(createReducer|handleActions|createSlice)\s*\(/.test(content)
  )
}

function extractReducerActions(content) {
  const actions = new Set()
  const addActions = (raw) => {
    for (const action of sagaActionNamesFromArg(raw)) {
      if (!action || action === 'default') continue
      actions.add(action)
    }
  }

  for (const match of content.matchAll(/\bcase\s+([^:\n]+)\s*:/g)) addActions(match[1])
  for (const match of content.matchAll(/\[\s*([^\]\n]+)\s*\]\s*:/g)) addActions(match[1])
  for (const match of content.matchAll(/\baddCase\s*\(\s*([^,\n)]+)/g)) addActions(match[1])
  for (const match of content.matchAll(/\bon\s*\(\s*([^,\n)]+)/g)) addActions(match[1])

  return Array.from(actions).sort()
}

module.exports = {
  cleanSqlTableName,
  extractFlowTargets,
  extractPythonFlowTargets,
  extractReducerActions,
  extractSagaEffects,
  looksLikeReducerFile,
  looksLikeSagaFile,
}
