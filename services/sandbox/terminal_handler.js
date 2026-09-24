'use strict'
// ──────────────────────────────────────────────────────────────
// Terminal web do sandbox (ex.: `claude login`), usado pelo admin via API.
//   POST   /terminal/sessions              { cols, rows } → { id }
//   GET    /terminal/sessions/:id/stream   NDJSON: {type:'output', data:<base64>} | {type:'exit', code}
//   POST   /terminal/sessions/:id/input    { data }
//   POST   /terminal/sessions/:id/resize   { cols, rows }
//   DELETE /terminal/sessions/:id
// Todos exigem X-Internal-Token = INTERNAL_API_TOKEN (só a API chama).
// O shell roda num pseudo-terminal (terminal_pty.py); sessões ociosas morrem.
// ──────────────────────────────────────────────────────────────

const crypto = require('crypto')
const { spawn } = require('child_process')

const PTY_SCRIPT = process.env.TERMINAL_PTY_SCRIPT || '/terminal_pty.py'
const MAX_SESSIONS = 3
const IDLE_MS = 15 * 60 * 1000
const BACKLOG_BYTES = 256 * 1024
const ROUTE = /^\/terminal\/sessions(?:\/([a-f0-9]{32})(?:\/(stream|input|resize))?)?$/

const sessions = new Map()

function authorized(req) {
  const expected = process.env.INTERNAL_API_TOKEN || ''
  const given = String(req.headers['x-internal-token'] || '')
  if (!expected || given.length !== expected.length) return false
  return crypto.timingSafeEqual(Buffer.from(given), Buffer.from(expected))
}

function clampSize(value, min, max, fallback) {
  const n = Number.parseInt(value, 10)
  return Number.isFinite(n) ? Math.max(min, Math.min(n, max)) : fallback
}

function touch(session) {
  clearTimeout(session.idleTimer)
  session.idleTimer = setTimeout(() => closeSession(session.id), IDLE_MS).unref()
}

function emit(session, event) {
  const line = JSON.stringify(event) + '\n'
  if (session.reader) {
    session.reader.write(line)
    return
  }
  // Sem ninguém lendo: guarda o fim da saída para quando o stream reconectar.
  session.backlog.push(line)
  session.backlogBytes += line.length
  while (session.backlogBytes > BACKLOG_BYTES && session.backlog.length > 1) {
    session.backlogBytes -= session.backlog.shift().length
  }
}

function createSession(cols, rows) {
  const id = crypto.randomBytes(16).toString('hex')
  const child = spawn('python3', [PTY_SCRIPT, String(cols), String(rows)], {
    cwd: process.env.HOME || '/root',
    env: { ...process.env, TERM: 'xterm-256color', COLORTERM: 'truecolor' },
    stdio: ['pipe', 'pipe', 'pipe', 'pipe'],
  })
  const session = { id, child, reader: null, backlog: [], backlogBytes: 0, exited: null, idleTimer: null }
  const output = (chunk) => emit(session, { type: 'output', data: chunk.toString('base64') })
  child.stdout.on('data', output)
  child.stderr.on('data', output)
  child.on('error', (err) => {
    emit(session, { type: 'output', data: Buffer.from(`Falha ao abrir o terminal: ${err.message}
`).toString('base64') })
    session.child.emit('exit', 127)
  })
  child.on('exit', (code) => {
    session.exited = code ?? 0
    emit(session, { type: 'exit', code: session.exited })
    if (session.reader) session.reader.end()
    setTimeout(() => sessions.delete(id), 60_000).unref()
  })
  sessions.set(id, session)
  touch(session)
  console.log(`[terminal] sessão ${id} aberta (${cols}x${rows})`)
  return session
}

function closeSession(id) {
  const session = sessions.get(id)
  if (!session) return false
  clearTimeout(session.idleTimer)
  if (session.exited === null) session.child.kill('SIGHUP')
  if (session.reader) session.reader.end()
  sessions.delete(id)
  console.log(`[terminal] sessão ${id} encerrada`)
  return true
}

function openStream(session, res) {
  if (session.reader) session.reader.end()
  res.writeHead(200, {
    'Content-Type': 'application/x-ndjson',
    'Cache-Control': 'no-store',
    'X-Accel-Buffering': 'no',
  })
  for (const line of session.backlog) res.write(line)
  session.backlog = []
  session.backlogBytes = 0
  if (session.exited !== null) {
    res.end(JSON.stringify({ type: 'exit', code: session.exited }) + '\n')
    return
  }
  session.reader = res
  res.on('close', () => {
    if (session.reader === res) session.reader = null
  })
}

/** Trata /terminal/*. Retorna true se tratou. */
async function tryHandle(req, res, { json, readBody }) {
  const pathname = new URL(req.url || '/', 'http://localhost').pathname
  if (!pathname.startsWith('/terminal/')) return false
  const reply = async (code, payload) => {
    await json(res, code, payload)
    return true
  }
  const match = pathname.match(ROUTE)
  if (!match) return reply(404, { error: 'Not found' })
  if (!authorized(req)) return reply(401, { error: 'unauthorized' })
  const [, id, action] = match

  if (!id) {
    if (req.method !== 'POST') return reply(405, { error: 'method not allowed' })
    if ([...sessions.values()].filter((s) => s.exited === null).length >= MAX_SESSIONS) {
      return reply(429, { error: `Limite de ${MAX_SESSIONS} terminais abertos no sandbox.` })
    }
    const body = await readBody(req)
    const session = createSession(clampSize(body.cols, 20, 500, 120), clampSize(body.rows, 5, 200, 32))
    return reply(200, { id: session.id })
  }

  const session = sessions.get(id)
  if (!session) return reply(404, { error: 'Terminal não encontrado ou já encerrado.' })
  touch(session)

  if (!action && req.method === 'DELETE') {
    closeSession(id)
    return reply(200, { ok: true })
  }
  if (action === 'stream' && req.method === 'GET') {
    openStream(session, res)
    return true
  }
  if (req.method !== 'POST') return reply(405, { error: 'method not allowed' })
  const body = await readBody(req)
  if (session.exited !== null) return reply(409, { error: 'O shell já terminou.' })
  if (action === 'input') {
    if (typeof body.data !== 'string') return reply(400, { error: 'data é obrigatório' })
    session.child.stdin.write(body.data)
  } else if (action === 'resize') {
    session.child.stdio[3].write(`${clampSize(body.cols, 20, 500, 120)} ${clampSize(body.rows, 5, 200, 32)}\n`)
  } else {
    return reply(404, { error: 'Not found' })
  }
  return reply(200, { ok: true })
}

module.exports = { tryHandle, _sessions: sessions, closeSession }
