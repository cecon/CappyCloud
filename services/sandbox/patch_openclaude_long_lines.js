'use strict'
// Patch do Read do openclaude: linhas gigantes.
//
// Arquivos como o tssnewnfse.json do TSS guardam templates inteiros em base64
// numa linha só (xml_rps, xml_depara, xml_canc). Uma leitura de 2 linhas já
// passa do limite de 25 mil tokens do Read, que recusa a leitura; depois de 3
// recusas o openclaude encerra o turno ("repeated tool failures"). O Read do
// Claude CLI corta linhas longas, este não.
//
// O patch corta cada linha em MAX_LINE_CHARS no que vai para o modelo e diz
// como ler o resto pelo Bash. O conteúdo guardado para Edit/listeners continua
// o original.
//   node /patch_openclaude_long_lines.js /openclaude/src/grpc/server.ts

const fs = require('fs')
const path = require('path')

const MARKER = 'CappyCloud long lines'
const MAX_LINE_CHARS = 2000

const VALIDATE_NEEDLE =
  '  await validateContentTokens(content, ext, maxTokens, {\n' +
  '    filePath: file_path,\n' +
  '    totalLines,\n' +
  '  })\n'

const VALIDATE_BLOCK =
  `  // ${MARKER}: o modelo recebe as linhas cortadas; readFileState fica com o original.\n` +
  '  const cappycloudShownContent = cappycloudClipLongLines(content, file_path, lineOffset)\n' +
  '  await validateContentTokens(cappycloudShownContent, ext, maxTokens, {\n' +
  '    filePath: file_path,\n' +
  '    totalLines,\n' +
  '  })\n'

const DATA_NEEDLE =
  "    type: 'text' as const,\n" +
  '    file: {\n' +
  '      filePath: file_path,\n' +
  '      content,\n'

const DATA_BLOCK =
  "    type: 'text' as const,\n" +
  '    file: {\n' +
  '      filePath: file_path,\n' +
  '      content: cappycloudShownContent,\n'

// Sem anotações de tipo: o mesmo texto roda no bun (server) e no node (testes).
const HELPER = `

// ${MARKER}: corta linhas acima de ${MAX_LINE_CHARS} caracteres e ensina a ler o resto.
function cappycloudClipLongLines(content, filePath, lineOffset) {
  if (typeof content !== 'string' || content.length <= ${MAX_LINE_CHARS}) return content
  const quoted = JSON.stringify(String(filePath))
  return content
    .split('\\n')
    .map((line, index) => {
      if (line.length <= ${MAX_LINE_CHARS}) return line
      const lineNumber = lineOffset + index + 1
      return (
        line.slice(0, ${MAX_LINE_CHARS}) +
        \`… [CappyCloud: linha \${lineNumber} tem \${line.length} caracteres; o Read mostra só os primeiros ${MAX_LINE_CHARS}. \` +
        \`Para ler o resto use o Bash: sed -n '\${lineNumber}p' \${quoted} | cut -c ${MAX_LINE_CHARS + 1}-8000. \` +
        \`Se for um campo base64 de JSON (xml_rps, xml_depara, xml_canc), decodifique com: \` +
        \`sed -n '\${lineNumber}p' \${quoted} | sed -E 's/^[^:]*: *"//; s/",?[[:space:]]*$//' | base64 -d]\`
      )
    })
    .join('\\n')
}
`

/** Devolve ``{ source, status }``; ``status`` é applied, present ou o needle que faltou. */
function patchSource(source) {
  if (source.includes(MARKER)) return { source, status: 'present' }
  if (!source.includes(VALIDATE_NEEDLE)) return { source, status: 'missing-validate' }
  if (!source.includes(DATA_NEEDLE)) return { source, status: 'missing-data' }
  const patched = source
    .replace(VALIDATE_NEEDLE, () => VALIDATE_BLOCK)
    .replace(DATA_NEEDLE, () => DATA_BLOCK)
  return { source: patched + HELPER, status: 'applied' }
}

function main(grpcServerFile) {
  const file = path.join(path.dirname(grpcServerFile), '..', 'tools', 'FileReadTool', 'FileReadTool.ts')
  const { source, status } = patchSource(fs.readFileSync(file, 'utf8'))
  if (status === 'applied') fs.writeFileSync(file, source)
  console.log(`[env_init] Read long lines patch: ${status}.`)
}

if (require.main === module) main(process.argv[2])

module.exports = { patchSource, MARKER, MAX_LINE_CHARS }
