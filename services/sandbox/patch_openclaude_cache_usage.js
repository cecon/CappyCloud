'use strict'
// Patch do gRPC do openclaude: tokens de cache no FinalResponse.
//
// O server soma input novo, leitura e gravação de cache em prompt_tokens e
// manda só esse total. Sem a separação a Cappy precifica todo o input a preço
// cheio, e a leitura de cache custa 10% disso. O patch guarda as duas parcelas
// e as envia em cache_read_tokens/cache_write_tokens (campos 4 e 5, iguais aos
// de proto/openclaude.proto do CappyCloud).
//   node /patch_openclaude_cache_usage.js /openclaude/src/grpc/server.ts

const fs = require('fs')
const path = require('path')

const MARKER = 'CappyCloud cache usage'

const SERVER_PATCHES = [
  {
    label: 'declaração',
    needle: '          let promptTokens = 0\n          let completionTokens = 0\n',
    replacement:
      '          let promptTokens = 0\n' +
      '          let completionTokens = 0\n' +
      `          // ${MARKER}: parcelas de cache dentro de promptTokens.\n` +
      '          let cappycloudCacheReadTokens = 0\n' +
      '          let cappycloudCacheWriteTokens = 0\n',
  },
  {
    label: 'soma',
    needle: '                promptTokens = freshInputTokens + cacheReadTokens + cacheCreationTokens\n',
    replacement:
      '                promptTokens = freshInputTokens + cacheReadTokens + cacheCreationTokens\n' +
      '                cappycloudCacheReadTokens = cacheReadTokens\n' +
      '                cappycloudCacheWriteTokens = cacheCreationTokens\n',
  },
  {
    label: 'done',
    needle: '                prompt_tokens: promptTokens,\n                completion_tokens: completionTokens\n',
    replacement:
      '                prompt_tokens: promptTokens,\n' +
      '                completion_tokens: completionTokens,\n' +
      '                cache_read_tokens: cappycloudCacheReadTokens,\n' +
      '                cache_write_tokens: cappycloudCacheWriteTokens\n',
  },
]

const PROTO_NEEDLE = '  uint32 prompt_tokens     = 2;\n  uint32 completion_tokens = 3;\n}'
const PROTO_REPLACEMENT =
  '  uint32 prompt_tokens     = 2;\n' +
  '  uint32 completion_tokens = 3;\n' +
  `  uint32 cache_read_tokens  = 4; // ${MARKER}\n` +
  '  uint32 cache_write_tokens = 5;\n}'

/** server.ts: ``{ source, status }``; ``status`` é applied, present ou missing-<parte>. */
function patchServerSource(source) {
  if (source.includes(MARKER)) return { source, status: 'present' }
  for (const { label, needle } of SERVER_PATCHES) {
    if (!source.includes(needle)) return { source, status: `missing-${label}` }
  }
  const patched = SERVER_PATCHES.reduce(
    (current, { needle, replacement }) => current.replace(needle, () => replacement),
    source,
  )
  return { source: patched, status: 'applied' }
}

/** openclaude.proto do sandbox: mesmos campos do proto do CappyCloud. */
function patchProtoSource(source) {
  if (source.includes(MARKER)) return { source, status: 'present' }
  if (!source.includes(PROTO_NEEDLE)) return { source, status: 'missing-final-response' }
  return { source: source.replace(PROTO_NEEDLE, () => PROTO_REPLACEMENT), status: 'applied' }
}

function main(grpcServerFile) {
  const protoFile = path.join(path.dirname(grpcServerFile), '..', 'proto', 'openclaude.proto')
  const server = patchServerSource(fs.readFileSync(grpcServerFile, 'utf8'))
  const proto = patchProtoSource(fs.readFileSync(protoFile, 'utf8'))
  // Os dois andam juntos: campo no done sem o proto seria descartado, e o contrário não mandaria nada.
  if (server.status.startsWith('missing') || proto.status.startsWith('missing')) {
    console.log(`[env_init] cache usage patch: server=${server.status} proto=${proto.status}, skipping.`)
    return
  }
  if (server.status === 'applied') fs.writeFileSync(grpcServerFile, server.source)
  if (proto.status === 'applied') fs.writeFileSync(protoFile, proto.source)
  console.log(`[env_init] cache usage patch: server=${server.status} proto=${proto.status}.`)
}

if (require.main === module) main(process.argv[2])

module.exports = { patchServerSource, patchProtoSource, MARKER }
