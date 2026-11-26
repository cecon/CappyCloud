'use strict'
// Patch do gRPC do openclaude: provedor isolado por conversa.
//
// O override de provedor (env_init.sh e patch_openclaude_anthropic_provider.js)
// grava URL, chave e formato em process.env no início de cada pedido e
// restaura os valores anteriores no fim. process.env é um só para o processo:
// com duas conversas ao mesmo tempo no sandbox, uma usava a chave da outra no
// meio da resposta (403/401 "Failed to authenticate", 2026-11-26), e o
// restaurar de quem terminava apagava a chave de quem continuava.
//
// O patch troca process.env por um Proxy. Dentro de um stream Chat, as
// variáveis de provedor (OPENAI_*, ANTHROPIC_*, CLAUDE_CODE_USE_*,
// CAPPYCLOUD_ANTHROPIC_*) são lidas e gravadas num escopo do stream, guardado
// em AsyncLocalStorage; o resto, e tudo fora de um stream, continua no
// process.env real. Os patches existentes seguem iguais: gravam e restauram,
// mas só no escopo da própria conversa.
//   node /patch_openclaude_provider_scope.js /openclaude/src/grpc/server.ts

const fs = require('fs')

const MARKER = 'CappyCloud provider scope'

const IMPORT_NEEDLE = "import * as grpc from '@grpc/grpc-js'\n"
const IMPORT_BLOCK = [
  "import * as grpc from '@grpc/grpc-js'",
  `// ${MARKER}: variáveis de provedor por stream Chat (ver patch_openclaude_provider_scope.js).`,
  "import { AsyncLocalStorage as CappyProviderStorage } from 'node:async_hooks'",
  'const cappyProviderStore = new CappyProviderStorage<Record<string, string | undefined>>()',
  'const CAPPY_PROVIDER_ENV = /^(OPENAI_|ANTHROPIC_|CLAUDE_CODE_USE_|CAPPYCLOUD_ANTHROPIC_)/',
  ';(() => {',
  '  const realEnv = process.env',
  '  const own = (o: object, k: PropertyKey) => Object.prototype.hasOwnProperty.call(o, k)',
  "  const scoped = (k: PropertyKey) => typeof k === 'string' && CAPPY_PROVIDER_ENV.test(k)",
  '  const scopeFor = (k: PropertyKey) => (scoped(k) ? cappyProviderStore.getStore() : undefined)',
  '  process.env = new Proxy(realEnv, {',
  '    get(t, k) { const s = scopeFor(k); return s && own(s, k) ? s[k as string] : Reflect.get(t, k) },',
  '    set(t, k, v) { const s = scopeFor(k); if (s) { s[k as string] = String(v); return true } return Reflect.set(t, k, v) },',
  '    deleteProperty(t, k) { const s = scopeFor(k); if (s) { s[k as string] = undefined; return true } return Reflect.deleteProperty(t, k) },',
  '    has(t, k) { const s = scopeFor(k); return s && own(s, k) ? s[k as string] !== undefined : Reflect.has(t, k) },',
  '    ownKeys(t) {',
  '      const keys = new Set(Reflect.ownKeys(t))',
  '      const s = cappyProviderStore.getStore()',
  '      if (s) for (const [k, v] of Object.entries(s)) { if (v === undefined) keys.delete(k); else keys.add(k) }',
  '      return [...keys]',
  '    },',
  '    getOwnPropertyDescriptor(t, k) {',
  '      const s = scopeFor(k)',
  '      if (!s || !own(s, k)) return Reflect.getOwnPropertyDescriptor(t, k)',
  '      const v = s[k as string]',
  '      return v === undefined ? undefined : { value: v, writable: true, enumerable: true, configurable: true }',
  '    },',
  '  })',
  '})()',
  '',
].join('\n')

const OPEN_NEEDLE = "    call.on('data', async (clientMessage) => {\n      try {\n"
const OPEN_REPLACEMENT =
  `    // ${MARKER}: cada stream Chat (uma conversa) tem o seu escopo de provedor.\n` +
  '    const cappyProviderScope: Record<string, string | undefined> = Object.create(null)\n' +
  "    call.on('data', (clientMessage) => cappyProviderStore.run(cappyProviderScope, async () => {\n" +
  '      try {\n'

const CLOSE_NEEDLE = "        call.end()\n      }\n    })\n\n    call.on('end', () => {\n"
const CLOSE_REPLACEMENT = "        call.end()\n      }\n    }))\n\n    call.on('end', () => {\n"

const PARTS = [
  { label: 'import', needle: IMPORT_NEEDLE, replacement: IMPORT_BLOCK },
  { label: 'abertura', needle: OPEN_NEEDLE, replacement: OPEN_REPLACEMENT },
  { label: 'fechamento', needle: CLOSE_NEEDLE, replacement: CLOSE_REPLACEMENT },
]

/** server.ts: ``{ source, status }``; ``status`` é applied, present ou missing-<parte>. */
function patchServerSource(source) {
  if (source.includes(MARKER)) return { source, status: 'present' }
  for (const { label, needle } of PARTS) {
    // Cada trecho precisa existir uma vez só, senão o wrap fecharia no lugar errado.
    if (source.split(needle).length !== 2) return { source, status: `missing-${label}` }
  }
  const patched = PARTS.reduce(
    (current, { needle, replacement }) => current.replace(needle, () => replacement),
    source,
  )
  return { source: patched, status: 'applied' }
}

function main(grpcServerFile) {
  const result = patchServerSource(fs.readFileSync(grpcServerFile, 'utf8'))
  if (result.status.startsWith('missing')) {
    console.log(`[env_init] provider scope patch: ${result.status}, skipping.`)
    return
  }
  if (result.status === 'applied') fs.writeFileSync(grpcServerFile, result.source)
  console.log(`[env_init] provider scope patch: ${result.status}.`)
}

if (require.main === module) main(process.argv[2] || '/openclaude/src/grpc/server.ts')

module.exports = { MARKER, patchServerSource }
