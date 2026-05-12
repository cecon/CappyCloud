'use strict'
// ──────────────────────────────────────────────────────────────
// Cliente mínimo de telemetria para Langfuse via HTTP ingestion API.
// Sem dependências npm — usa só fetch built-in.
// Desligado se LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY ausentes.
// ──────────────────────────────────────────────────────────────

const crypto = require('crypto')

const PUBLIC_KEY = process.env.LANGFUSE_PUBLIC_KEY || ''
const SECRET_KEY = process.env.LANGFUSE_SECRET_KEY || ''
const HOST = (process.env.LANGFUSE_HOST || 'http://cappycloud-langfuse-web:3000').replace(/\/$/, '')

const ENABLED = !!(PUBLIC_KEY && SECRET_KEY)

function isEnabled() {
  return ENABLED
}

function uuid() {
  return crypto.randomUUID()
}

function authHeader() {
  return 'Basic ' + Buffer.from(`${PUBLIC_KEY}:${SECRET_KEY}`).toString('base64')
}

async function sendBatch(events) {
  if (!ENABLED || !events.length) return
  try {
    const resp = await fetch(`${HOST}/api/public/ingestion`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': authHeader(),
      },
      body: JSON.stringify({ batch: events }),
    })
    if (!resp.ok) {
      const text = await resp.text()
      console.warn(`[langfuse] ingestion HTTP ${resp.status}: ${text.slice(0, 200)}`)
    }
  } catch (err) {
    console.warn(`[langfuse] ingestion failed: ${err.message}`)
  }
}

// Loga uma chamada LLM standalone (cria trace + generation em uma chamada).
// Retorna sem aguardar — fire-and-forget.
function logGeneration({
  name = 'llm_call',
  model,
  input,
  output,
  usage,
  startTime,
  endTime,
  level = 'DEFAULT',
  statusMessage,
  metadata,
  tags = [],
}) {
  if (!ENABLED) return
  const traceId = uuid()
  const generationId = uuid()
  const now = new Date().toISOString()
  const events = [
    {
      id: uuid(),
      type: 'trace-create',
      timestamp: now,
      body: {
        id: traceId,
        name,
        input,
        output,
        metadata,
        tags: ['sandbox', ...tags],
      },
    },
    {
      id: uuid(),
      type: 'generation-create',
      timestamp: now,
      body: {
        id: generationId,
        traceId,
        name,
        model,
        input,
        output,
        usage,
        startTime: startTime || now,
        endTime: endTime || now,
        level,
        statusMessage,
        metadata,
      },
    },
  ]
  // Fire and forget.
  sendBatch(events).catch(() => {})
}

module.exports = { isEnabled, logGeneration }
