'use strict'
// Configuração do Claude Agent SDK para o runtime claude_cli: onde está o SDK,
// sessões guardadas por conversa, ambiente do CLI e o servidor MCP `cappy`.

const fs = require('fs')
const path = require('path')
const { execFileSync } = require('child_process')
const { pathToFileURL } = require('url')

const CONFIG_DIR = process.env.CLAUDE_CONFIG_DIR || path.join(process.env.HOME || '/root', '.claude')
const SESSIONS_FILE = path.join(CONFIG_DIR, 'cappycloud-sessions.json')
const OPENCLAUDE_CONFIG = path.join(process.env.HOME || '/root', '.openclaude.json')
// Variáveis do openclaude (provider OpenAI-compatível) que não podem vazar para o CLI oficial.
const STRIPPED_ENV = /^(OPENAI_|CLAUDE_CODE_USE_OPENAI$|CLAUDE_CODE_PROVIDER_PROFILE_ENV_APPLIED$)/
// Servidor MCP `cappy`: a busca de evidências, memória e grafo sob demanda
// (antes a API fazia tudo antes do turno). Só leitura, então não pede aprovação.
const EVIDENCE_DIR = process.env.CAPPY_TOOLS_DIR || '/opt/cappy_tools'
const EVIDENCE_TOOLS = ['mcp__cappy__buscar_evidencias', 'mcp__cappy__consultar_conhecimento_workspace']

let sdkPromise = null

const SDK_PACKAGE = '@anthropic-ai/claude-agent-sdk'

/**
 * Caminho do entrypoint ESM do SDK instalado globalmente. Nem import() nem
 * require.resolve() acham o pacote via NODE_PATH (o `exports` dele só expõe a
 * condição `default` para .mjs), então procuramos o package.json nas raízes globais.
 */
function sdkEntry() {
  const roots = [...(process.env.NODE_PATH || '').split(path.delimiter), '/usr/local/lib/node_modules']
  for (const root of roots.filter(Boolean)) {
    const pkgDir = path.join(root, SDK_PACKAGE)
    const pkg = readJson(path.join(pkgDir, 'package.json'), null)
    if (!pkg) continue
    const exported = pkg.exports && pkg.exports['.']
    const target = (exported && (exported.import || exported.default)) || pkg.main || 'sdk.mjs'
    return path.join(pkgDir, target)
  }
  throw new Error(`${SDK_PACKAGE} não está instalado no sandbox`)
}

function loadSdk() {
  if (!sdkPromise) {
    sdkPromise = import(pathToFileURL(sdkEntry()).href)
    sdkPromise.catch(() => { sdkPromise = null })
  }
  return sdkPromise
}

function claudeExecutable() {
  try {
    return execFileSync('sh', ['-c', 'command -v claude'], { encoding: 'utf8' }).trim() || null
  } catch {
    return null
  }
}

function readJson(file, fallback) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')) } catch { return fallback }
}

// Valor por conversa: { session_id, totals } (antes era só o id da sessão).
function storedSession(conversationKey) {
  const raw = conversationKey ? readJson(SESSIONS_FILE, {})[conversationKey] : null
  if (!raw) return { sessionId: null, totals: null }
  if (typeof raw === 'string') return { sessionId: raw, totals: null }
  return { sessionId: raw.session_id || null, totals: raw.totals || null }
}

function rememberSession(conversationKey, sessionId, totals = null) {
  if (!conversationKey) return
  const sessions = readJson(SESSIONS_FILE, {})
  if (sessionId) sessions[conversationKey] = { session_id: sessionId, totals }
  else delete sessions[conversationKey]
  fs.mkdirSync(CONFIG_DIR, { recursive: true })
  fs.writeFileSync(SESSIONS_FILE, JSON.stringify(sessions, null, 2), 'utf8')
}

/** Servidor `cappy` com o contexto da conversa (repos, worktrees, Confluence). */
function evidenceServer(toolContext) {
  if (!toolContext || typeof toolContext !== 'object') return {}
  return {
    cappy: {
      type: 'stdio',
      command: 'python3',
      args: [path.join(EVIDENCE_DIR, 'evidence_mcp_server.py')],
      // Descrição completa no prompt desde o 1º passo, sem passar pelo ToolSearch:
      // escondida, o modelo só vê o nome e quase nunca escolhe a ferramenta sozinho.
      alwaysLoad: true,
      env: {
        CAPPY_TOOL_CONTEXT: JSON.stringify(toolContext),
        PYTHONPATH: EVIDENCE_DIR,
        SESSION_SERVER_PORT: process.env.SESSION_SERVER_PORT || '8080',
      },
    },
  }
}

function sdkEnv() {
  const env = {}
  for (const [key, value] of Object.entries(process.env)) {
    if (!STRIPPED_ENV.test(key)) env[key] = value
  }
  env.CLAUDE_CONFIG_DIR = CONFIG_DIR
  env.IS_SANDBOX = '1'
  // A sessão acaba com o turno: subagente/Bash em segundo plano morreria sem
  // entregar o resultado ("aguarde um instante" e nada mais). Tudo roda no turno.
  env.CLAUDE_CODE_DISABLE_BACKGROUND_TASKS = '1'
  // Compacta a conversa ao chegar perto deste tamanho, em vez da janela "auto"
  // do modelo (que pode ir a 1M): cada passo do agente relê a janela inteira.
  env.CLAUDE_CODE_AUTO_COMPACT_WINDOW = process.env.CLAUDE_CODE_AUTO_COMPACT_WINDOW || '150000'
  return env
}

module.exports = {
  CONFIG_DIR,
  EVIDENCE_TOOLS,
  OPENCLAUDE_CONFIG,
  claudeExecutable,
  evidenceServer,
  loadSdk,
  readJson,
  rememberSession,
  sdkEntry,
  sdkEnv,
  storedSession,
}
