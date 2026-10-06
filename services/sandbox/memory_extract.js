'use strict'
// Gravação automática da memória do workspace ao fim de cada turno.
//
//   POST /memory/extract  {workspace, question, answer, model?}   (X-Internal-Token)
//
// O agente quase nunca grava por conta própria, então o pipeline chama esta rota
// depois do "done". Um passo separado do Claude (sem ferramentas, uma volta) lê
// a pergunta e a resposta, compara com o que já está gravado e devolve só o que
// foi confirmado no código ou na documentação. Cada item vira uma memória.

const { saveMemory, searchMemory, createClient } = require('./memory_handler')

const MAX_ITEMS = 3
const MAX_QUESTION = 4000
const MAX_ANSWER = 14000
const TYPES = ['fact', 'bug', 'architecture', 'pattern', 'workflow']

const SYSTEM = `Você mantém a memória compartilhada de uma equipe que usa um agente de código num workspace.
Recebe uma pergunta, a resposta do agente e o que já está gravado. Devolva SOMENTE um array JSON (pode ser vazio []).

Grave apenas conhecimento durável e confirmado na resposta, útil para as próximas conversas do workspace:
- onde algo está implementado (arquivos, funções, tabelas);
- regra de negócio ou fluxo confirmado no código ou na documentação;
- causa de um bug e onde corrigir.

Não grave:
- suposição, hipótese ou trecho com "provavelmente", "pode ser", "não confirmado";
- assunto da pessoa (pedido, opinião, tarefa do dia) ou passo a passo da conversa;
- o que já está gravado, mesmo com outras palavras;
- segredos, senhas, tokens, dados de clientes (nomes, CNPJ, CPF, valores de notas).

Cada item: {"type": "fact|bug|architecture|pattern|workflow", "content": "1 a 4 frases em português, autossuficientes, com nomes de arquivos/funções", "files": ["repo/caminho"], "concepts": ["termo", ...]}.
No máximo ${MAX_ITEMS} itens. Se nada atender às regras, devolva [].`

function buildPrompt({ question, answer, existing }) {
  const known = existing.length
    ? existing.map((m) => `- ${m.content}`).join('\n')
    : '(nada gravado sobre isso)'
  return [
    `## Já gravado\n${known}`,
    `## Pergunta\n${String(question).slice(0, MAX_QUESTION)}`,
    `## Resposta do agente\n${String(answer).slice(0, MAX_ANSWER)}`,
    'Devolva o array JSON.',
  ].join('\n\n')
}

/** Primeiro array JSON do texto do modelo; itens fora do formato são descartados. */
function parseItems(text) {
  const start = String(text || '').indexOf('[')
  const end = String(text || '').lastIndexOf(']')
  if (start < 0 || end <= start) return []
  let parsed
  try { parsed = JSON.parse(text.slice(start, end + 1)) } catch { return [] }
  if (!Array.isArray(parsed)) return []
  return parsed
    .filter((item) => item && typeof item.content === 'string' && item.content.trim().length >= 20)
    .slice(0, MAX_ITEMS)
    .map((item) => ({
      type: TYPES.includes(item.type) ? item.type : 'fact',
      content: item.content.trim(),
      files: Array.isArray(item.files) ? item.files.map(String) : [],
      concepts: Array.isArray(item.concepts) ? item.concepts.map(String) : [],
    }))
}

/** Uma volta do Claude CLI (login do sandbox), sem ferramentas nem CLAUDE.md. */
async function askClaude(prompt, model) {
  const runtime = require('./claude_runtime_handler')
  const { modelAlias } = require('./claude_runtime_mapper')
  const { query } = await runtime.loadSdk()
  const stream = query({
    prompt,
    options: {
      model: modelAlias(model).alias,
      maxTurns: 1,
      // Sem ferramentas: só lê o texto (e não carrega ~18 mil tokens de definições).
      tools: [],
      settingSources: [],
      systemPrompt: SYSTEM,
      cwd: '/tmp',
      pathToClaudeCodeExecutable: runtime.claudeExecutable(),
      env: runtime.sdkEnv(),
    },
  })
  let text = ''
  for await (const message of stream) {
    if (message.type === 'assistant') {
      for (const block of message.message?.content || []) if (block.type === 'text') text += block.text
    }
    if (message.type === 'result') break
  }
  return text
}

async function extractAndSave(call, { workspace, question, answer, model }, ask = askClaude) {
  if (!String(answer || '').trim() || !String(question || '').trim()) return { saved: 0, memories: [] }
  // O que já existe sobre o assunto entra no prompt para não gravar repetido.
  const related = await searchMemory(call, { workspace, q: String(question).slice(0, 300), limit: 5 })
    .then((found) => found.results)
    .catch(() => [])
  const items = parseItems(await ask(buildPrompt({ question, answer, existing: related }), model))
  const memories = []
  for (const item of items) {
    const { id } = await saveMemory(call, { workspace, ...item })
    memories.push({ id, type: item.type, content: item.content })
  }
  return { saved: memories.length, memories }
}

async function tryHandle(req, res, { json, readBody }, call = createClient()) {
  if (req.method !== 'POST' || (req.url || '').split('?')[0] !== '/memory/extract') return false
  const { authorized } = require('./claude_runtime_handler')
  if (!authorized(req)) {
    json(res, 401, { error: 'unauthorized' })
    return true
  }
  try {
    const result = await extractAndSave(call, await readBody(req))
    if (result.saved) console.log(`[memory_extract] ${result.saved} memória(s) gravada(s)`)
    json(res, 200, result)
  } catch (err) {
    console.error(`[memory_extract] ${err.message}`)
    json(res, err.status || 500, { error: err.message })
  }
  return true
}

module.exports = { askClaude, buildPrompt, extractAndSave, parseItems, tryHandle }
