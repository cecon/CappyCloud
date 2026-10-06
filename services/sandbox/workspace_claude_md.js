'use strict'
// Seção fixa do CLAUDE.md de cada workspace: como buscar em arquivos, usar o grafo
// e a memória. Fica no CLAUDE.md (e não só no prompt da primeira mensagem) para
// valer em toda conversa, inclusive retomadas e subagentes.

// O agente roda no mesmo container do session_server (porta fixa nos stacks).
const MEMORY_URL = 'http://127.0.0.1:8080/memory'

function toolsSection(slug) {
  const root = `/repos/workspaces/${slug}`
  const graph = `${root}/knowledge/graphify/graph.json`
  return `## Ferramentas do workspace (gerado pelo CappyCloud — não edite)

### Buscar em arquivos
- Os repositórios ficam em \`${root}/repos/<alias>\` (links) e, quando editáveis, também como worktree na pasta da sessão.
- Busque texto com \`rg -L -n "<termo>" ${root}/repos/\`. O \`-L\` é obrigatório: sem ele o rg não entra nos links e devolve vazio.
- Liste arquivos com \`rg -L --files ${root}/repos/<alias> | rg "<padrão>"\`; leia com a ferramenta Read (em partes, se o arquivo for grande).
- Não use \`grep -r\` nem \`find\` amplos: são lentos e entram em \`graphify-out/\` (índice gerado, centenas de MB). O rg já ignora essa pasta.
- Pergunta simples: responda você mesmo com poucas buscas focadas, sem delegar a subagentes.

### Grafo de código (graphify)
Gerado da branch principal de cada repositório; não reflete mudanças desta conversa.
- \`graphify query "<pergunta>" --graph ${graph} --budget 1500\`
- \`graphify explain "<símbolo>" --graph ${graph}\`
- Visão geral: \`${root}/knowledge/graphify/<alias>/GRAPH_REPORT.md\`
Linguagens que o graphify não lê (ex.: ADVPL/TLPP) não entram no grafo: se ele não souber, busque com rg.

### Memória do workspace (agentmemory)
Compartilhada entre as conversas deste workspace. Busque antes de investigar do zero:
\`curl -s -G ${MEMORY_URL}/search --data-urlencode workspace=${slug} --data-urlencode 'q=<termos>'\` (sem resultados = nada gravado sobre isso).
A gravação é automática: ao fim de cada resposta o CappyCloud guarda o que foi confirmado no código. Para gravar algo explicitamente:
\`curl -s -X POST ${MEMORY_URL}/save -H 'Content-Type: application/json' -d '{"workspace":"${slug}","type":"fact","content":"<o que lembrar>","files":"<alias>/<caminho>"}'\`
Não grave segredos nem dados de clientes. Se a memória responder erro, siga sem ela.
`
}

/** CLAUDE.md final: instruções do admin + seção de ferramentas. */
function composeClaudeMd(slug, adminText) {
  const own = String(adminText || '').trim()
  return [own, toolsSection(slug)].filter(Boolean).join('\n\n')
}

module.exports = { composeClaudeMd, toolsSection }
